"""Faz F.3 — Gıda Temas Mevzuatı Kütüphanesi. EU-10-2011 SADECE bir referans/
citation satırıdır -- `applicable_packaging_types` boş bırakıldığı için
Aşama 3'ün (assess_regulations) kategori eşleşmesiyle otomatik süpürülmez,
bu yüzden mevcut mevzuat değerlendirme akışını etkilemez (ayrıca doğrulanır)."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.knowledge_base.loader import load_all
from app.main import app
from app.models.food_contact_requirement import FoodContactRequirement
from app.models.knowledge import Regulation
from app.models.recipe import PackagingRequest
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


def test_eu_10_2011_regulation_row_loaded(db_session):
    load_all(db_session)
    reg = db_session.query(Regulation).filter_by(code="EU-10-2011").one_or_none()
    assert reg is not None
    assert reg.applicable_packaging_types == []


def test_food_contact_requirements_loaded_and_linked(db_session):
    load_all(db_session)
    reg = db_session.query(Regulation).filter_by(code="EU-10-2011").one()
    rows = db_session.query(FoodContactRequirement).filter_by(regulation_id=reg.id).all()
    assert len(rows) == 3
    by_type = {r.requirement_type: r for r in rows}
    assert by_type["genel_migrasyon"].limit_value == 10
    assert by_type["genel_migrasyon"].limit_unit == "mg_dm2"
    assert by_type["genel_migrasyon"].applies_to_pcr is False
    # SML madde bazlıdır -- tek bir sayı uydurulmadı.
    assert by_type["spesifik_migrasyon"].limit_value is None
    assert by_type["pcr_dekontaminasyon"].applies_to_pcr is True
    assert by_type["pcr_dekontaminasyon"].limit_value is None


def test_food_contact_requirement_loader_is_idempotent(db_session):
    load_all(db_session)
    count_first = db_session.query(FoodContactRequirement).count()
    load_all(db_session)
    count_second = db_session.query(FoodContactRequirement).count()
    assert count_first == count_second == 3


def test_applies_to_pcr_filter(db_session):
    load_all(db_session)
    pcr_rows = db_session.query(FoodContactRequirement).filter_by(applies_to_pcr=True).all()
    assert len(pcr_rows) == 1
    assert pcr_rows[0].requirement_type == "pcr_dekontaminasyon"


def test_eu_10_2011_does_not_appear_in_regulatory_assessment(db_session):
    """EU-10-2011'in applicable_packaging_types boş olması, Aşama 3
    değerlendirmesine (Faz A/B davranışı) yeni bir kart eklemediğini
    kanıtlar -- assess_regulations'a hiç dokunulmadı."""
    load_all(db_session)
    req = PackagingRequest(
        packaging_type="plastik tabak", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 200, "width_mm": 200},
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)

    overall, assessments = assess_regulations(db_session, req)

    codes = {db_session.get(Regulation, a.regulation_id).code for a in assessments}
    assert "EU-10-2011" not in codes


def test_reference_food_contact_requirements_endpoint(client, db_session):
    load_all(db_session)
    resp = client.get("/api/v1/reference/food-contact-requirements")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    assert all(r["is_demo_placeholder"] for r in body)
