"""Faz T.1d (Madde 31) — Nihai Rapor'un mevcut "İklim ve Döngüsellik
Perspektifi" (§14) bölümü, Faz S.1'in geri dönüşüm rehberiyle
zenginleştirildi (DPP'de zaten vardı, rapor hiç okumuyordu). REUSE, yeni
hesaplama yok."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.knowledge import Material, Polymer
from app.models.production import SustainabilityResult
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.recycling_guidance_service import build_recycling_guidance
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
    return recipe


def test_recycling_guidance_matches_service_exactly(db_session):
    material = _material(db_session)
    recipe = _recipe(db_session, material)

    expected = build_recycling_guidance(recipe)
    data = build_optimization_report_data(db_session, recipe.id)

    assert data["geri_donusum_rehberi"] == expected
    assert "sertifikasyonu" in data["geri_donusum_rehberi"]["aciklama"]


def test_http_pdf_report_renders_with_recycling_guidance(client, db_session):
    material = _material(db_session)
    recipe = _recipe(db_session, material)

    resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/optimization-report")
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"
