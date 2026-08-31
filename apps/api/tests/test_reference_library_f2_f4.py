"""Faz F.2 + F.4 — Mevzuat Eşik Yapılandırma + Kimyasal Kısıtlar Kütüphanesi.
`packaging_service.py`'nin PFAS (PPWR-ART-5) verdict mantığı DEĞİŞMEDİ --
sadece reasoning artık ChemicalRestriction'dan gerçek limit sayılarını
alıntılıyor (bkz. test_regulations_content.py'deki mevcut PFAS testleri,
onlar da kırılmadan geçiyor)."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.knowledge_base.loader import load_all
from app.main import app
from app.models.chemical_restriction import ChemicalRestriction
from app.models.knowledge import Regulation
from app.models.recipe import PackagingRequest
from app.models.regulation_requirement import RegulationRequirement
from app.services.packaging_service import assess_regulations


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _request(db, food_contact=True, packaging_type="plastik tabak"):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test", target_market="AB",
        food_contact=food_contact, target_volume_units=1000, dimensions={"length_mm": 200, "width_mm": 200},
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


# --- F.2: yapılandırılmış eşik alanları -------------------------------

def test_ppwr_art7_rows_carry_structured_threshold(db_session):
    load_all(db_session)
    rows = db_session.query(RegulationRequirement).filter_by(
        packaging_category="gida_temasli_pet_disi_plastik"
    ).order_by(RegulationRequirement.target_year).all()
    assert len(rows) == 2
    assert rows[0].target_year == 2030
    assert rows[0].threshold_value == 10.0
    assert rows[0].threshold_unit == "%_pcr_icerik"
    assert rows[1].target_year == 2040
    assert rows[1].threshold_value == 25.0


def test_other_regulation_requirement_rows_have_no_threshold(db_session):
    """Md.6/Md.9/Md.10 gibi sayısal bir eşik taşımayan maddeler için
    threshold_value None kalmalı -- uydurma bir sayı atanmaz."""
    load_all(db_session)
    row = db_session.query(RegulationRequirement).join(Regulation).filter(
        Regulation.code == "PPWR-ART-6"
    ).one()
    assert row.threshold_value is None
    assert row.threshold_unit is None


# --- F.4: ChemicalRestriction kütüphanesi -------------------------------

def test_pfas_chemical_restrictions_loaded_and_linked_to_regulation(db_session):
    load_all(db_session)
    reg = db_session.query(Regulation).filter_by(code="PPWR-ART-5").one()
    rows = db_session.query(ChemicalRestriction).filter_by(regulation_id=reg.id).all()
    assert len(rows) == 3
    by_type = {r.restriction_type: r for r in rows}
    assert by_type["tekil_madde_siniri"].limit_value == 25
    assert by_type["tekil_madde_siniri"].limit_unit == "ppb"
    assert by_type["toplam_hedef"].limit_value == 250
    assert by_type["toplam_sinir"].limit_value == 50
    assert by_type["toplam_sinir"].limit_unit == "ppm"
    assert all(r.food_contact_only for r in rows)
    assert all(r.is_demo_placeholder for r in rows)


def test_chemical_restriction_loader_is_idempotent(db_session):
    load_all(db_session)
    count_first = db_session.query(ChemicalRestriction).count()
    load_all(db_session)
    count_second = db_session.query(ChemicalRestriction).count()
    assert count_first == count_second == 3


# --- PFAS reasoning artık yapılandırılmış veriden geliyor ---------------

def test_pfas_reasoning_cites_structured_limit_values(db_session):
    load_all(db_session)
    req = _request(db_session, food_contact=True)

    overall, assessments = assess_regulations(db_session, req)

    pfas = next(
        a for a in assessments if db_session.get(Regulation, a.regulation_id).code == "PPWR-ART-5"
    )
    assert "25 ppb" in pfas.reasoning
    assert "250 ppb" in pfas.reasoning
    assert "50 ppm" in pfas.reasoning
    # Faz A'dan kalan mevcut sözleşme (test_regulations_content.py) hâlâ geçerli:
    assert "PFAS" in pfas.reasoning
    assert "İnceleme Gerekli" in pfas.reasoning
    # Verdict mantığı DEĞİŞMEDİ -- hâlâ requirement satırının default_verdict'i.
    assert pfas.verdict == "inceleme_gerekli"


# --- Yeni /reference/* uçları --------------------------------------------

def test_reference_regulation_requirements_endpoint(client, db_session):
    load_all(db_session)
    resp = client.get("/api/v1/reference/regulation-requirements")
    assert resp.status_code == 200
    body = resp.json()
    art7_rows = [r for r in body if r["packaging_category"] == "gida_temasli_pet_disi_plastik"]
    assert {r["threshold_value"] for r in art7_rows} == {10.0, 25.0}


def test_reference_chemical_restrictions_endpoint(client, db_session):
    load_all(db_session)
    resp = client.get("/api/v1/reference/chemical-restrictions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    assert all(r["substance_group"] == "PFAS" for r in body)
