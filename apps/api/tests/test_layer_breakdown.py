"""Faz B.3 — katman bazlı reçete gösterimi (Dashboard 8). Regresyon: Dashboard
7'de '%69 Virgin / %31 PCR' görünüyordu ama PCR'ın HANGİ KATMANDA olduğu
görünmüyordu. Bu testler, Dashboard 8'in `ComparisonOut`'unun artık katman
bazlı kırılım taşıdığını ve PCR'ın doğru katmanda raporlandığını doğrular."""
import pytest

from app.models.knowledge import Material, PcrMaterial, Polymer
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.production_flow_service import build_comparison


def _seed_recipe_with_pcr_in_core_layer(db_session):
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()

    virgin = Material(
        polymer_id=polymer.id, name="LDPE Virgin", material_type="virgin", density_g_cm3=0.92,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=34.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    pcr = PcrMaterial(
        polymer_id=polymer.id, name="LLDPE PCR", material_type="pcr", density_g_cm3=0.92,
        degradation_factor=0.08, food_contact_eligible=True, max_recommended_ratio_pct=50.0,
        cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=0.6,
    )
    db_session.add_all([virgin, pcr])
    db_session.flush()

    request = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="test",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 400, "width_mm": 300},
    )
    db_session.add(request)
    db_session.flush()

    recipe = Recipe(
        packaging_request_id=request.id, version=1, source="sistem_uretti", status="onerildi",
        total_micron=70.0,
    )
    db_session.add(recipe)
    db_session.flush()

    # Katman A (dış, %15): tamamen virgin. Katman B (çekirdek, %70): %30 PCR.
    # Katman A (iç, %15): tamamen virgin. -- kullanıcının verdiği örneğe benzer.
    db_session.add_all([
        RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=virgin.id, ratio_pct=100.0, thickness_micron=10.5),
        RecipeLayer(recipe_id=recipe.id, layer_index=1, layer_label="B", material_id=virgin.id, ratio_pct=70.0, thickness_micron=49.0),
        RecipeLayer(recipe_id=recipe.id, layer_index=1, layer_label="B", material_id=pcr.id, ratio_pct=30.0, thickness_micron=49.0),
        RecipeLayer(recipe_id=recipe.id, layer_index=2, layer_label="A", material_id=virgin.id, ratio_pct=100.0, thickness_micron=10.5),
    ])
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


def test_comparison_includes_layer_breakdown_showing_which_layer_has_pcr(db_session):
    recipe = _seed_recipe_with_pcr_in_core_layer(db_session)

    comparison = build_comparison(db_session, recipe)

    layers = comparison["recommended"]["layers"]
    assert len(layers) == 3  # 3 farklı layer_index (A, B, A)

    core_layer = next(l for l in layers if l["layer_index"] == 1)
    outer_layers = [l for l in layers if l["layer_index"] != 1]

    core_types = {m["material_type"] for m in core_layer["materials"]}
    assert "pcr" in core_types  # PCR çekirdek (B) katmanında

    for outer in outer_layers:
        outer_types = {m["material_type"] for m in outer["materials"]}
        assert "pcr" not in outer_types  # dış katmanlarda PCR YOK


def test_layer_breakdown_ratios_sum_to_100_within_each_layer(db_session):
    recipe = _seed_recipe_with_pcr_in_core_layer(db_session)
    comparison = build_comparison(db_session, recipe)

    for layer in comparison["recommended"]["layers"]:
        total = sum(m["ratio_pct"] for m in layer["materials"])
        assert total == pytest.approx(100.0)


def test_layer_breakdown_carries_material_names_not_just_ids(db_session):
    recipe = _seed_recipe_with_pcr_in_core_layer(db_session)
    comparison = build_comparison(db_session, recipe)

    core_layer = next(l for l in comparison["recommended"]["layers"] if l["layer_index"] == 1)
    names = {m["material_name"] for m in core_layer["materials"]}
    assert "LLDPE PCR" in names
    assert "LDPE Virgin" in names
