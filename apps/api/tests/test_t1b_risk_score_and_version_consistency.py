"""Faz T.1b (Madde 31) — Nihai Rapor'a Üretim Öncesi Risk Skoru (Faz Q.1,
Faz R.3'ün tedarikçi radarı 8. bileşen olarak dahil) + Faz L.1'in karar izi
eklendi. T.4 (Madde 31): `_ppwr_section()`'ın versiyon sorgusu artık
`_current_requirement_version()` (packaging_service.py) ile AYNI sıralamayı
kullanıyor -- çok satırlı bir mevzuat maddesinde rapor ve DPP/§22 ARTIK
aynı 'güncel versiyon'u gösteriyor."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.knowledge import Material, Polymer, Regulation
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer, RegulatoryAssessment
from app.models.regulation_requirement import RegulationRequirement
from app.services.packaging_service import _current_requirement_version
from app.services.report_service import build_optimization_report_data


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _material(db):
    polymer = db.query(Polymer).filter_by(code="PE").one_or_none()
    if polymer is None:
        polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
        db.add(polymer)
        db.flush()
    m = Material(
        polymer_id=polymer.id, name="Test Malzeme", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(m)
    db.flush()
    return m


def _recipe(db, material):
    from app.models.production import SustainabilityResult

    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(packaging_request_id=req.id, version=1, source="sistem_uretti", status="dogrulandi", is_verified=True, total_micron=70.0)
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0))
    db.add(SustainabilityResult(recipe_id=recipe.id, per_1000_units={"virgin_kg": 10.0, "pcr_kg": 0.0, "regranul_kg": 0.0, "karbon_kg_co2": 18.0, "fire_kg": 1.0, "enerji_kwh": 5.0}, is_actual=True))
    db.commit()
    db.refresh(recipe)
    return recipe, req


def test_risk_score_flows_into_report_with_all_8_components(db_session):
    material = _material(db_session)
    recipe, _ = _recipe(db_session, material)

    data = build_optimization_report_data(db_session, recipe.id)

    risk = data["risk_skoru"]
    assert risk["genel_risk"] in ("dusuk", "orta", "yuksek")
    assert set(risk["bilesenler"].keys()) == {
        "yeni_hammadde", "pcr_seviyesi", "kalinlik_azaltimi", "makine_uyumu",
        "gecmis_uretim_benzerligi", "teknik_performans", "mevzuat_kanit_eksikleri",
        "tedarikci_kanit_tamligi",
    }


def test_decision_trail_flows_into_ppwr_section(db_session):
    material = _material(db_session)
    recipe, req = _recipe(db_session, material)

    reg = Regulation(code="PPWR-ART-88", title="Test Madde", category="test", description="d")
    db_session.add(reg)
    db_session.flush()
    trail = {"hedef_pazar": "AB", "uygulanan_madde": "PPWR-ART-88", "hedef_tarih": "2030"}
    db_session.add(RegulatoryAssessment(
        packaging_request_id=req.id, regulation_id=reg.id, verdict="uygun_gorunuyor", reasoning="t",
        decision_trail=trail,
    ))
    db_session.commit()

    data = build_optimization_report_data(db_session, recipe.id)

    item = next(i for i in data["ppwr_on_uyum"]["items"] if i["regulation_code"] == "PPWR-ART-88")
    assert item["decision_trail"] == trail


def test_ppwr_section_version_matches_current_requirement_version_for_multi_row_regulation(db_session):
    """Faz T.4 — çok satırlı bir madde (ör. PPWR Md.7'nin 2030/2040
    kırılımı) için §12'nin gösterdiği versiyon, `_current_requirement_
    version()`'ın (§22/DPP'nin de kullandığı KANONİK kaynak) döndürdüğüyle
    BİREBİR aynı olmalı."""
    material = _material(db_session)
    recipe, req = _recipe(db_session, material)

    reg = Regulation(code="PPWR-ART-77", title="Çok Satırlı Test Madde", category="test", description="d")
    db_session.add(reg)
    db_session.flush()
    db_session.add(RegulationRequirement(
        regulation_id=reg.id, regulation_no="EU 1", article="Md.7", sub_article="2030", target_year=2030,
        requirement_text="t1", version="1.0",
    ))
    db_session.add(RegulationRequirement(
        regulation_id=reg.id, regulation_no="EU 1", article="Md.7", sub_article="2040", target_year=2040,
        requirement_text="t2", version="2.0",
    ))
    db_session.add(RegulatoryAssessment(
        packaging_request_id=req.id, regulation_id=reg.id, verdict="uygun_gorunuyor", reasoning="t",
    ))
    db_session.commit()

    data = build_optimization_report_data(db_session, recipe.id)
    item = next(i for i in data["ppwr_on_uyum"]["items"] if i["regulation_code"] == "PPWR-ART-77")

    canonical = _current_requirement_version(db_session, reg.id)
    assert item["requirement_version"] == canonical
    assert item["requirement_version"] == "1.0"  # en erken target_year (2030) satırı


def test_http_pdf_report_still_renders_with_risk_section(client, db_session):
    material = _material(db_session)
    recipe, _ = _recipe(db_session, material)

    resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/optimization-report")
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"
