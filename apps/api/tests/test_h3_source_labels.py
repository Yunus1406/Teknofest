"""Faz H.3 — Aşama 12'nin "Gerçekleşen" bloğu Virgin/PCR/Regranül/Karbon
(reçete kompozisyonundan HESAPLANAN) ile Fire/Enerji'yi (GERÇEKTEN canlı
üretim verisinden, bugün her zaman simülasyon) tek bir etikette
karıştırmamalı. Bu testler `kutle_veri_kaynagi`/`fire_enerji_veri_kaynagi`
alanlarının hem `finalize_result` (Aşama 12) hem `estimate_stage8_breakdown`
(Aşama 8) çıktısında doğru ve tutarlı şekilde ayrı ayrı dolduğunu doğrular."""
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.production import PhysicalTest, ProductionOrder
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.production_flow_service import (
    estimate_stage8_breakdown,
    finalize_result,
    simulate_live_data,
)


def _seed_recipe_with_line(db_session):
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()
    material = Material(
        polymer_id=polymer.id, name="PE Virgin Film Sınıfı", material_type="virgin", density_g_cm3=0.92,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=34.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    db_session.add(material)
    db_session.flush()

    line = ProductionLine(
        name="Test Hat", process_type="Blown Film Extrusion", layer_structure="A",
        layer_count=1, min_micron=20, max_micron=100, line_speed_m_min=50,
        energy_kwh_per_kg=0.4, average_waste_rate_pct=3.0, active=True,
    )
    db_session.add(line)
    db_session.flush()

    request = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="test",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 400, "width_mm": 300},
    )
    db_session.add(request)
    db_session.flush()

    recipe = Recipe(
        packaging_request_id=request.id, version=1, source="sistem_uretti", status="onerildi",
        total_micron=70.0, line_id=line.id,
    )
    db_session.add(recipe)
    db_session.flush()
    db_session.add(
        RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0)
    )
    db_session.add(
        PhysicalTest(recipe_id=recipe.id, test_type="kalinlik", value=70.0, unit="mikron", target_min=63.0, target_max=77.0, result="basarili", passed=True)
    )
    db_session.commit()
    db_session.refresh(recipe)
    return recipe, line


def test_estimate_stage8_mass_source_is_hesaplanan(db_session):
    recipe, line = _seed_recipe_with_line(db_session)
    per_1000 = estimate_stage8_breakdown(db_session, recipe)
    assert per_1000["kutle_veri_kaynagi"] == "hesaplanan"
    assert per_1000["fire_enerji_veri_kaynagi"] == "hesaplanan"


def test_finalize_result_mass_source_is_hesaplanan(db_session):
    recipe, line = _seed_recipe_with_line(db_session)
    result = finalize_result(db_session, recipe)
    assert result.per_1000_units["kutle_veri_kaynagi"] == "hesaplanan"


def test_finalize_result_fire_energy_source_is_none_without_production(db_session):
    """Hiç üretim/canlı veri yokken fire/enerji zaten None -- kaynak
    etiketi de uydurulmamalı, None kalmalı."""
    recipe, line = _seed_recipe_with_line(db_session)
    result = finalize_result(db_session, recipe)
    assert result.per_1000_units["fire_kg"] is None
    assert result.per_1000_units["fire_enerji_veri_kaynagi"] is None


def test_finalize_result_fire_energy_source_reflects_real_live_data_source(db_session):
    """Fire/enerji GERÇEKTEN simüle üretim verisinden geldiğinde, kaynak
    etiketi bunu doğru şekilde 'simulasyon_verisi' olarak yansıtmalı --
    Virgin/PCR/Karbon'un 'hesaplanan' etiketiyle KARIŞTIRILMAMALI."""
    recipe, line = _seed_recipe_with_line(db_session)
    order = ProductionOrder(recipe_id=recipe.id, line_id=line.id, scheduled_qty_units=500)
    db_session.add(order)
    db_session.commit()
    simulate_live_data(db_session, order, ticks=2)

    result = finalize_result(db_session, recipe)
    per_1000 = result.per_1000_units

    assert per_1000["fire_kg"] is not None
    assert per_1000["fire_enerji_veri_kaynagi"] == "simulasyon_verisi"
    assert per_1000["kutle_veri_kaynagi"] == "hesaplanan"
    # İki etiket kasıtlı olarak FARKLI -- Faz A'daki çelişki (bir ekranda
    # simülasyon derken başka bir ekranda gerçekleşen gibi görünme) burada
    # asla oluşamaz.
    assert per_1000["fire_enerji_veri_kaynagi"] != per_1000["kutle_veri_kaynagi"]
