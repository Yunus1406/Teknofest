"""Faz H.4 — Aşama 12'nin üç sütunlu karşılaştırması (Referans | Tahmini |
Gerçekleşen). `build_triple_comparison` üçünü de AYNI birimde (1000 birim
başına kg) döner. Bu testler: (a) referans yokken reference/gains'in None
kaldığını (uydurulmadığını), (b) finalize edilmeden önce gerçekleşen'in None
olduğunu, (c) finalize sonrası gerçekleşen'in dolduğunu, (d) bir referans
reçete varken onun KENDİ is_actual=True satırının yeniden hesaplanmadan
okunduğunu, (e) azaltım yüzdesinin doğru hesaplandığını doğrular."""
import pytest

from app.models.knowledge import Material, Polymer
from app.models.production import PhysicalTest
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.production_flow_service import build_triple_comparison, finalize_result


def _seed_recipe(db_session, virgin_material, packaging_type="esnek film ambalaj", thickness=70.0):
    request = PackagingRequest(
        packaging_type=packaging_type, usage_area="kuru gıda poşetleme", product="atıştırmalık poşeti",
        target_market="yurt içi", food_contact=True, target_volume_units=1000,
        dimensions={"length_mm": 400, "width_mm": 300},
    )
    db_session.add(request)
    db_session.flush()

    recipe = Recipe(
        packaging_request_id=request.id, version=1, source="sistem_uretti", status="onerildi",
        total_micron=thickness,
    )
    db_session.add(recipe)
    db_session.flush()
    db_session.add(
        RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=virgin_material.id, ratio_pct=100.0, thickness_micron=thickness)
    )
    db_session.add(
        PhysicalTest(recipe_id=recipe.id, test_type="kalinlik", value=thickness, unit="mikron", target_min=thickness * 0.9, target_max=thickness * 1.1, result="basarili", passed=True)
    )
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


def _seed_material(db_session, name="PE Virgin Film Sınıfı", carbon=1.8):
    polymer = Polymer(code=f"PE-{name}", name="Polietilen", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()
    material = Material(
        polymer_id=polymer.id, name=name, material_type="virgin", density_g_cm3=0.92,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=34.0, carbon_factor_kg_co2_per_kg=carbon,
    )
    db_session.add(material)
    db_session.flush()
    return material


def test_no_reference_when_no_other_verified_recipe_of_same_type(db_session):
    material = _seed_material(db_session)
    recipe = _seed_recipe(db_session, material)

    triple = build_triple_comparison(db_session, recipe)

    assert triple["reference"] is None
    assert triple["gains"] is None
    assert triple["tahmini"]["virgin_kg"] is not None


def test_gerceklesen_is_none_before_finalize(db_session):
    material = _seed_material(db_session)
    recipe = _seed_recipe(db_session, material)

    triple = build_triple_comparison(db_session, recipe)

    assert triple["gerceklesen"] is None


def test_gerceklesen_populated_after_finalize(db_session):
    material = _seed_material(db_session)
    recipe = _seed_recipe(db_session, material)
    finalize_result(db_session, recipe)

    triple = build_triple_comparison(db_session, recipe)

    assert triple["gerceklesen"] is not None
    assert triple["gerceklesen"]["virgin_kg"] is not None


def test_reference_reused_from_existing_sustainability_result_not_recomputed(db_session):
    material = _seed_material(db_session, name="PE Referans", carbon=2.0)
    reference_recipe = _seed_recipe(db_session, material)
    reference_result = finalize_result(db_session, reference_recipe)

    target = _seed_recipe(db_session, material)
    triple = build_triple_comparison(db_session, target)

    assert triple["reference"] is not None
    assert triple["reference"] == reference_result.per_1000_units


def test_gains_computed_when_reference_and_gerceklesen_both_exist(db_session):
    high_carbon = _seed_material(db_session, name="PE Referans Yüksek Karbon", carbon=3.0)
    reference_recipe = _seed_recipe(db_session, high_carbon)
    finalize_result(db_session, reference_recipe)

    low_carbon = _seed_material(db_session, name="PE Düşük Karbon", carbon=1.0)
    target = _seed_recipe(db_session, low_carbon)
    finalize_result(db_session, target)

    triple = build_triple_comparison(db_session, target)

    assert triple["gains"] is not None
    assert triple["gains"]["karbon_azaltimi_pct"] > 0  # düşük karbonlu malzeme -> gerçek azaltım


def test_gains_none_when_no_reference_even_if_gerceklesen_exists(db_session):
    material = _seed_material(db_session)
    recipe = _seed_recipe(db_session, material)
    finalize_result(db_session, recipe)

    triple = build_triple_comparison(db_session, recipe)

    assert triple["reference"] is None
    assert triple["gerceklesen"] is not None
    assert triple["gains"] is None
