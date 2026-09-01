"""Faz P.2 (Madde 21) — Otomatik Eko-Tasarım Önerileri. Her öneri GERÇEK
veriden türetilir; yeterli veri/eşik yoksa öneri türü hiç üretilmez (boş
liste normal, uydurma bir şablon metin ASLA yazılmaz)."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Additive, Material, Polymer, Regulation
from app.models.recipe import PackagingRequest, Recipe, RecipeAdditive, RecipeLayer, RegulatoryAssessment
from app.services.eco_design_service import build_eco_design_suggestions


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _polymer(db, code):
    p = db.query(Polymer).filter_by(code=code).one_or_none()
    if p is None:
        p = Polymer(code=code, name=code, category="poliolefin", base_properties={})
        db.add(p)
        db.flush()
    return p


def _material(db, code, material_type="virgin", max_recommended_ratio_pct=100.0, name=None):
    polymer = _polymer(db, code)
    m = Material(
        polymer_id=polymer.id, name=name or f"{code} {material_type}", material_type=material_type,
        food_contact_eligible=True, max_recommended_ratio_pct=max_recommended_ratio_pct,
        cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(m)
    db.flush()
    return m


def _line(db, min_micron=20.0, max_micron=100.0):
    line = ProductionLine(name="Test Hat P2a", layer_structure="A", layer_count=1, min_micron=min_micron, max_micron=max_micron)
    db.add(line)
    db.flush()
    return line


def _recipe(db, line=None, total_micron=70.0, food_contact=True):
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test ürün", target_market="AB",
        food_contact=food_contact, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, line_id=line.id if line else None, source="sistem_uretti",
        status="onerildi", is_verified=False, total_micron=total_micron,
    )
    db.add(recipe)
    db.flush()
    return recipe


def _add_layer(db, recipe, material, layer_index, layer_label, ratio_pct=100.0, thickness_micron=70.0):
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=layer_index, layer_label=layer_label, material_id=material.id, ratio_pct=ratio_pct, thickness_micron=thickness_micron))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_no_suggestions_when_no_signal_present(db_session):
    virgin = _material(db_session, "PE")
    recipe = _recipe(db_session, line=None)
    recipe = _add_layer(db_session, recipe, virgin, 0, "A")

    suggestions = build_eco_design_suggestions(db_session, recipe)
    assert suggestions == []


def test_kalinlik_azaltma_suggested_when_above_line_min(db_session):
    virgin = _material(db_session, "PE")
    line = _line(db_session, min_micron=30.0, max_micron=100.0)
    recipe = _recipe(db_session, line=line, total_micron=70.0)
    recipe = _add_layer(db_session, recipe, virgin, 0, "A")

    suggestions = build_eco_design_suggestions(db_session, recipe)
    keys = [s["key"] for s in suggestions]
    assert "kalinlik_azaltma" in keys
    dim = next(s for s in suggestions if s["key"] == "kalinlik_azaltma")
    assert "40" in dim["detay_metni"]  # 70-30 marj


def test_kalinlik_azaltma_not_suggested_when_already_at_line_min(db_session):
    virgin = _material(db_session, "PE")
    line = _line(db_session, min_micron=70.0, max_micron=100.0)
    recipe = _recipe(db_session, line=line, total_micron=70.0)
    recipe = _add_layer(db_session, recipe, virgin, 0, "A")

    suggestions = build_eco_design_suggestions(db_session, recipe)
    assert "kalinlik_azaltma" not in [s["key"] for s in suggestions]


def test_mono_material_suggested_for_multi_polymer_recipe(db_session):
    pe = _material(db_session, "PE")
    pp = _material(db_session, "PP")
    recipe = _recipe(db_session, line=None)
    db_session.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=pe.id, ratio_pct=100.0, thickness_micron=35.0))
    db_session.add(RecipeLayer(recipe_id=recipe.id, layer_index=1, layer_label="B", material_id=pp.id, ratio_pct=100.0, thickness_micron=35.0))
    db_session.commit()
    db_session.refresh(recipe)

    suggestions = build_eco_design_suggestions(db_session, recipe)
    assert "mono_material_donusum" in [s["key"] for s in suggestions]


def test_pcr_artirma_suggested_when_below_ceiling(db_session):
    pcr = _material(db_session, "PE", material_type="pcr", max_recommended_ratio_pct=40.0)
    recipe = _recipe(db_session, line=None)
    db_session.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=pcr.id, ratio_pct=20.0, thickness_micron=70.0))
    db_session.commit()
    db_session.refresh(recipe)

    suggestions = build_eco_design_suggestions(db_session, recipe)
    pcr_suggestions = [s for s in suggestions if s["key"].startswith("pcr_artirma")]
    assert len(pcr_suggestions) == 1
    assert "%20" in pcr_suggestions[0]["detay_metni"]


def test_gereksiz_katman_suggested_for_duplicate_material(db_session):
    pe = _material(db_session, "PE")
    recipe = _recipe(db_session, line=None)
    db_session.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=pe.id, ratio_pct=100.0, thickness_micron=35.0))
    db_session.add(RecipeLayer(recipe_id=recipe.id, layer_index=1, layer_label="B", material_id=pe.id, ratio_pct=100.0, thickness_micron=35.0))
    db_session.commit()
    db_session.refresh(recipe)

    suggestions = build_eco_design_suggestions(db_session, recipe)
    assert "gereksiz_katman_azaltimi" in [s["key"] for s in suggestions]


def test_masterbatch_suggested_near_dosage_ceiling(db_session):
    virgin = _material(db_session, "PE")
    recipe = _recipe(db_session, line=None)
    recipe = _add_layer(db_session, recipe, virgin, 0, "A")
    additive = Additive(name="Beyaz Masterbatch", additive_type="masterbatch", dosage_min_pct=0.5, dosage_max_pct=2.0)
    db_session.add(additive)
    db_session.flush()
    db_session.add(RecipeAdditive(recipe_id=recipe.id, additive_id=additive.id, dosage_pct=1.9))
    db_session.commit()

    suggestions = build_eco_design_suggestions(db_session, recipe)
    assert any(s["key"].startswith("masterbatch_") for s in suggestions)


def test_masterbatch_not_suggested_when_far_from_ceiling(db_session):
    virgin = _material(db_session, "PE")
    recipe = _recipe(db_session, line=None)
    recipe = _add_layer(db_session, recipe, virgin, 0, "A")
    additive = Additive(name="Beyaz Masterbatch", additive_type="masterbatch", dosage_min_pct=0.5, dosage_max_pct=2.0)
    db_session.add(additive)
    db_session.flush()
    db_session.add(RecipeAdditive(recipe_id=recipe.id, additive_id=additive.id, dosage_pct=0.6))
    db_session.commit()

    suggestions = build_eco_design_suggestions(db_session, recipe)
    assert not any(s["key"].startswith("masterbatch_") for s in suggestions)


def test_recyclability_suggestions_use_real_criterion_text_not_numeric_score(db_session):
    virgin = _material(db_session, "PE")
    recipe = _recipe(db_session, line=None)
    recipe = _add_layer(db_session, recipe, virgin, 0, "A")

    reg = Regulation(code="PPWR-ART-6", title="Geri Dönüştürülebilirlik", category="geri_donusturulebilirlik", description="test")
    db_session.add(reg)
    db_session.flush()
    db_session.add(
        RegulatoryAssessment(
            packaging_request_id=recipe.packaging_request_id, regulation_id=reg.id,
            verdict="uygun_gorunuyor", reasoning="test",
            recyclability_breakdown={"dimensions": [{"dimension": "tasarim_uyumu", "criterion_text": "Mono-material yapı tercih edilmelidir.", "weight_pct": 40.0, "packaging_category": None}]},
        )
    )
    db_session.commit()

    suggestions = build_eco_design_suggestions(db_session, recipe)
    recyclability = [s for s in suggestions if s["key"].startswith("geri_donusturulebilirlik_")]
    assert len(recyclability) == 1
    assert recyclability[0]["detay_metni"] == "Mono-material yapı tercih edilmelidir."


def test_http_eco_design_endpoint(client, db_session):
    virgin = _material(db_session, "PE")
    line = _line(db_session, min_micron=30.0)
    recipe = _recipe(db_session, line=line, total_micron=70.0)
    recipe = _add_layer(db_session, recipe, virgin, 0, "A")

    resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/eco-design-suggestions")
    assert resp.status_code == 200, resp.text
    assert any(s["key"] == "kalinlik_azaltma" for s in resp.json())
