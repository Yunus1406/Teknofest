"""Faz H.1 — Aşama 8'in "Tahmini" mutlak kütle dengesi (virgin/pcr/regranül/
fire/enerji kg). `estimate_stage8_breakdown` Aşama 12'nin de kullandığı
`compute_mass_breakdown()` ile AYNI fiziği kullanır; fire/enerji ise henüz
üretim olmadığından hattın NOMİNAL katsayılarından tahmin edilir. Bu testler:
(a) ölçü/yoğunluk verisi varken virgin/pcr/karbon'un gerçekten hesaplandığını,
(b) hat eşleşmemişken fire/enerji'nin None kaldığını (uydurulmadığını),
(c) hat eşleşip nominal katsayıları varken fire/enerji'nin doğru formülle
hesaplandığını, (d) fonksiyonun idempotent olduğunu (tekrar çağrıldığında
yeni bir SustainabilityResult satırı biriktirmediğini) doğrular."""
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.production import SustainabilityResult
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.production_flow_service import build_comparison, estimate_stage8_breakdown


def _seed_recipe(db_session, with_dims=True):
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()

    virgin = Material(
        polymer_id=polymer.id, name="LDPE Virgin", material_type="virgin", density_g_cm3=0.92,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=34.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    db_session.add(virgin)
    db_session.flush()

    dims = {"length_mm": 400, "width_mm": 300} if with_dims else {}
    request = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="test",
        food_contact=True, target_volume_units=1000, dimensions=dims,
    )
    db_session.add(request)
    db_session.flush()

    recipe = Recipe(
        packaging_request_id=request.id, version=1, source="sistem_uretti", status="onerildi",
        total_micron=70.0,
    )
    db_session.add(recipe)
    db_session.flush()
    db_session.add(
        RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=virgin.id, ratio_pct=100.0, thickness_micron=70.0)
    )
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


def _seed_line(db_session, waste_pct=3.5, energy_per_kg=0.4):
    line = ProductionLine(
        name="Test Hat", process_type="Blown Film Extrusion", layer_structure="A",
        layer_count=1, min_micron=20, max_micron=100, line_speed_m_min=50,
        energy_kwh_per_kg=energy_per_kg, average_waste_rate_pct=waste_pct, active=True,
    )
    db_session.add(line)
    db_session.commit()
    db_session.refresh(line)
    return line


def test_mass_fields_computed_when_dims_and_density_present(db_session):
    recipe = _seed_recipe(db_session)
    per_1000 = estimate_stage8_breakdown(db_session, recipe)
    assert per_1000["virgin_kg"] is not None
    assert per_1000["virgin_kg"] > 0
    assert per_1000["pcr_kg"] == 0.0  # bu reçetede hiç PCR yok
    assert per_1000["karbon_kg_co2"] is not None


def test_fire_and_energy_none_when_no_line_matched(db_session):
    recipe = _seed_recipe(db_session)
    assert recipe.line_id is None
    per_1000 = estimate_stage8_breakdown(db_session, recipe)
    assert per_1000["fire_kg"] is None
    assert per_1000["enerji_kwh"] is None


def test_fire_and_energy_estimated_from_line_nominal_rates(db_session):
    recipe = _seed_recipe(db_session)
    line = _seed_line(db_session, waste_pct=5.0, energy_per_kg=0.5)
    recipe.line_id = line.id
    db_session.commit()

    per_1000 = estimate_stage8_breakdown(db_session, recipe)
    assert per_1000["fire_kg"] is not None
    assert per_1000["enerji_kwh"] is not None
    # total_mass_kg == virgin_kg burada (tek malzeme, tamamı virgin)
    total_mass_kg = per_1000["virgin_kg"]
    assert per_1000["fire_kg"] == round(total_mass_kg * 0.05, 3)
    assert per_1000["enerji_kwh"] == round(total_mass_kg * 0.5, 3)


def test_mass_fields_none_when_dimensions_missing_no_fabrication(db_session):
    recipe = _seed_recipe(db_session, with_dims=False)
    per_1000 = estimate_stage8_breakdown(db_session, recipe)
    assert per_1000["virgin_kg"] is None
    assert per_1000["pcr_kg"] is None
    assert per_1000["fire_kg"] is None
    assert "_uyari" in per_1000


def test_estimate_is_idempotent_no_duplicate_rows(db_session):
    recipe = _seed_recipe(db_session)
    first = estimate_stage8_breakdown(db_session, recipe)
    second = estimate_stage8_breakdown(db_session, recipe)
    assert first == second
    rows = db_session.query(SustainabilityResult).filter_by(recipe_id=recipe.id, is_actual=False).all()
    assert len(rows) == 1


def test_build_comparison_recommended_side_carries_mass_fields(db_session):
    recipe = _seed_recipe(db_session)
    comparison = build_comparison(db_session, recipe)
    recommended = comparison["recommended"]
    assert recommended["virgin_kg"] is not None
    assert recommended["is_estimated"] is True
