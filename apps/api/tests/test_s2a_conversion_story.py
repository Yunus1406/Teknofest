"""Faz S.2 (Madde 30) — Bir Ambalajın Dönüşüm Hikâyesi. Sadece doğrulanmış
reçeteler için üretilir; 6 sabit aşama, hiçbir aşama yeni bir hesaplama
YAPMAZ — hepsi report_service.py fonksiyonlarını AYNEN reuse eder."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.production import PhysicalTest, ProductionOrder
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.production_flow_service import build_comparison
from app.services.report_service import build_executive_summary, build_optimization_report_data
from app.services.story_service import build_conversion_story


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _polymer(db):
    p = db.query(Polymer).filter_by(code="PE").one_or_none()
    if p is None:
        p = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
        db.add(p)
        db.flush()
    return p


def _material(db):
    polymer = _polymer(db)
    m = Material(
        polymer_id=polymer.id, name="Test Malzeme", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(m)
    db.flush()
    return m


def _line(db):
    line = ProductionLine(name="Hat-1", layer_structure="A", layer_count=1, min_micron=10.0, max_micron=200.0)
    db.add(line)
    db.flush()
    return line


def _recipe(db, material, line=None, is_verified=True, total_micron=70.0):
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, line_id=line.id if line else None, source="sistem_uretti",
        status="dogrulandi" if is_verified else "onerildi", is_verified=is_verified, total_micron=total_micron,
    )
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=total_micron))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_unknown_recipe_returns_none(db_session):
    assert build_conversion_story(db_session, "olmayan-id") is None


def test_unverified_recipe_raises_value_error(db_session):
    material = _material(db_session)
    recipe = _recipe(db_session, material, is_verified=False)

    with pytest.raises(ValueError):
        build_conversion_story(db_session, recipe.id)


def test_minimal_verified_recipe_has_six_stages_and_honest_absence(db_session):
    material = _material(db_session)
    line = _line(db_session)
    recipe = _recipe(db_session, material, line=line)

    story = build_conversion_story(db_session, recipe.id)

    assert story["recipe_id"] == recipe.id
    keys = [s["key"] for s in story["stages"]]
    assert keys == ["baslangic", "oneri", "uretim", "dogrulama", "sonuc", "mevzuat"]

    baslangic = next(s for s in story["stages"] if s["key"] == "baslangic")
    assert baslangic["veri"]["has_reference"] is False

    uretim = next(s for s in story["stages"] if s["key"] == "uretim")
    assert uretim["veri"]["line"]["name"] == "Hat-1"
    assert uretim["veri"]["orders"] == []

    dogrulama = next(s for s in story["stages"] if s["key"] == "dogrulama")
    assert dogrulama["veri"]["ozet"] == {"basarili": 0, "basarisiz": 0, "beklemede": 0}


def test_dogrulama_stage_counts_real_physical_tests(db_session):
    material = _material(db_session)
    line = _line(db_session)
    recipe = _recipe(db_session, material, line=line)
    db_session.add(PhysicalTest(recipe_id=recipe.id, test_type="kalinlik", value=70.0, unit="mikron", target_min=60.0, target_max=80.0, result="basarili", passed=True))
    db_session.add(PhysicalTest(recipe_id=recipe.id, test_type="gramaj", value=10.0, unit="g/m2", result="beklemede", passed=False))
    db_session.commit()

    story = build_conversion_story(db_session, recipe.id)
    dogrulama = next(s for s in story["stages"] if s["key"] == "dogrulama")
    assert dogrulama["veri"]["ozet"] == {"basarili": 1, "basarisiz": 0, "beklemede": 1}


def test_uretim_stage_counts_real_production_orders(db_session):
    material = _material(db_session)
    line = _line(db_session)
    recipe = _recipe(db_session, material, line=line)
    db_session.add(ProductionOrder(recipe_id=recipe.id, line_id=line.id, status="tamamlandi", scheduled_qty_units=100))
    db_session.commit()

    story = build_conversion_story(db_session, recipe.id)
    uretim = next(s for s in story["stages"] if s["key"] == "uretim")
    assert len(uretim["veri"]["orders"]) == 1


def test_sonuc_stage_matches_build_executive_summary_exactly(db_session):
    """Faz A'nın 'referans varsa %, yoksa mutlak' kuralı SADECE
    build_executive_summary'de uygulanır -- story_service burada YENİDEN
    hesaplama yapmamalı, birebir aynı sonucu taşımalı."""
    material = _material(db_session)
    line = _line(db_session)
    recipe = _recipe(db_session, material, line=line)

    comparison = build_comparison(db_session, recipe)
    expected = build_executive_summary(db_session, recipe, comparison)

    story = build_conversion_story(db_session, recipe.id)
    sonuc = next(s for s in story["stages"] if s["key"] == "sonuc")
    assert sonuc["veri"] == expected


def test_report_data_includes_additive_story_key_without_removing_existing(db_session):
    material = _material(db_session)
    line = _line(db_session)
    recipe = _recipe(db_session, material, line=line)

    data = build_optimization_report_data(db_session, recipe.id)

    assert "donusum_hikayesi" in data
    assert data["donusum_hikayesi"]["recipe_id"] == recipe.id
    # Mevcut anahtarlar (Faz A-R) BOZULMADI.
    assert "kapak" in data
    assert "yonetici_ozeti" in data
    assert "referans_recete" in data


def test_http_conversion_story_endpoint(client, db_session):
    material = _material(db_session)
    line = _line(db_session)
    recipe = _recipe(db_session, material, line=line)

    resp = client.get(f"/api/v1/traceability/recipes/{recipe.id}/conversion-story")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["stages"]) == 6


def test_http_conversion_story_400_for_unverified_recipe(client, db_session):
    material = _material(db_session)
    recipe = _recipe(db_session, material, is_verified=False)

    resp = client.get(f"/api/v1/traceability/recipes/{recipe.id}/conversion-story")
    assert resp.status_code == 400


def test_http_conversion_story_404_for_unknown_recipe(client):
    resp = client.get("/api/v1/traceability/recipes/olmayan-id/conversion-story")
    assert resp.status_code == 404


def test_pdf_report_renders_with_story_section(client, db_session):
    material = _material(db_session)
    line = _line(db_session)
    recipe = _recipe(db_session, material, line=line)

    resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/optimization-report")
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"
