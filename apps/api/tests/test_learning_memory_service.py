"""Faz I.3 — Gerçek Öğrenme Hafızası Mekanizması. `diff_recipe_compositions`
GERÇEK bir fark verildiğinde doğru hesaplar; `causal_chain_for_recipe`
`version_history()`'nin zincirini kompozisyon farkı + hat + gerçek fire/
enerji + fiziksel test özeti + sonuçla zenginleştirir; `change_outcome_stats`
tüm reçete geçişlerini kaba değişiklik türlerine ayırıp doğrulandı/revizyon
oranını sayar. Bugünkü GERÇEK üretim akışında (submit_physical_tests) bir
revizyon ebeveynden birebir kopyalandığından bu, "değişiklik yok" bucket'ının
dürüstçe dolduğunu da doğrular — mekanizmanın kendisi ayrı testlerle
(gerçek bir fark verildiğinde) doğru çalıştığı kanıtlanır."""
import pytest

from app.models.infrastructure import ProductionLine
from app.models.knowledge import Additive, Material, Polymer
from app.models.production import PhysicalTest, ProductionOrder
from app.models.recipe import PackagingRequest, Recipe, RecipeAdditive, RecipeLayer
from app.services.learning_memory_service import (
    causal_chain_for_recipe,
    change_outcome_stats,
    diff_recipe_compositions,
)
from app.services.production_flow_service import simulate_live_data, submit_physical_tests


def _polymer_and_materials(db):
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    virgin = Material(
        polymer_id=polymer.id, name="PE Virgin", material_type="virgin", density_g_cm3=0.92,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    pcr = Material(
        polymer_id=polymer.id, name="PE PCR", material_type="pcr", density_g_cm3=0.92,
        degradation_factor=0.08, food_contact_eligible=True, max_recommended_ratio_pct=50.0,
        cost_per_kg=26.0, carbon_factor_kg_co2_per_kg=0.6,
    )
    db.add_all([virgin, pcr])
    db.flush()
    return virgin, pcr


def _recipe_with_layer(db, material, ratio_pct=100.0, thickness=70.0, version=1, parent_recipe_id=None):
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="t", product="t", target_market="t",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=version, source="sistem_uretti", status="onerildi",
        total_micron=thickness, parent_recipe_id=parent_recipe_id,
    )
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=ratio_pct, thickness_micron=thickness))
    db.commit()
    db.refresh(recipe)
    return recipe


# --- diff_recipe_compositions: gerçek farkları doğru bulur ------------------

def test_diff_empty_when_identical(db_session):
    virgin, _ = _polymer_and_materials(db_session)
    old = _recipe_with_layer(db_session, virgin)
    new = _recipe_with_layer(db_session, virgin)  # aynı oran/kalınlık
    assert diff_recipe_compositions(old, new) == []


def test_diff_detects_material_ratio_change(db_session):
    virgin, pcr = _polymer_and_materials(db_session)
    old = _recipe_with_layer(db_session, virgin, ratio_pct=100.0)
    new = Recipe(packaging_request_id=old.packaging_request_id, version=2, source="sistem_uretti", status="taslak", total_micron=70.0)
    db_session.add(new)
    db_session.flush()
    db_session.add(RecipeLayer(recipe_id=new.id, layer_index=0, layer_label="A", material_id=virgin.id, ratio_pct=75.0, thickness_micron=70.0))
    db_session.add(RecipeLayer(recipe_id=new.id, layer_index=0, layer_label="A", material_id=pcr.id, ratio_pct=25.0, thickness_micron=70.0))
    db_session.commit()
    db_session.refresh(new)

    diff = diff_recipe_compositions(old, new)
    types = {d["tur"] for d in diff}
    assert "malzeme_orani_degisti" in types
    pcr_change = next(d for d in diff if d.get("material_id") == pcr.id)
    assert pcr_change["eski_deger"] is None
    assert pcr_change["yeni_deger"] == 25.0
    virgin_change = next(d for d in diff if d.get("material_id") == virgin.id)
    assert virgin_change["eski_deger"] == 100.0
    assert virgin_change["yeni_deger"] == 75.0


def test_diff_detects_thickness_change(db_session):
    virgin, _ = _polymer_and_materials(db_session)
    old = _recipe_with_layer(db_session, virgin, thickness=70.0)
    new = _recipe_with_layer(db_session, virgin, thickness=85.0)

    diff = diff_recipe_compositions(old, new)
    thickness_changes = [d for d in diff if d["tur"] == "kalinlik_degisti"]
    assert len(thickness_changes) == 1
    assert thickness_changes[0]["eski_deger"] == 70.0
    assert thickness_changes[0]["yeni_deger"] == 85.0


def test_diff_detects_added_layer(db_session):
    virgin, _ = _polymer_and_materials(db_session)
    old = _recipe_with_layer(db_session, virgin)
    new = _recipe_with_layer(db_session, virgin)
    db_session.add(RecipeLayer(recipe_id=new.id, layer_index=1, layer_label="B", material_id=virgin.id, ratio_pct=100.0, thickness_micron=20.0))
    db_session.commit()
    db_session.refresh(new)

    diff = diff_recipe_compositions(old, new)
    assert any(d["tur"] == "katman_eklendi" and d["layer_index"] == 1 for d in diff)


def test_diff_detects_additive_dosage_change(db_session):
    virgin, _ = _polymer_and_materials(db_session)
    additive = Additive(name="Kayganlaştırıcı", additive_type="slip", dosage_min_pct=0.1, dosage_max_pct=1.0, food_contact_eligible=True, cost_per_kg=60.0)
    db_session.add(additive)
    db_session.flush()

    old = _recipe_with_layer(db_session, virgin)
    db_session.add(RecipeAdditive(recipe_id=old.id, additive_id=additive.id, dosage_pct=0.2, layer_index=0))
    new = _recipe_with_layer(db_session, virgin)
    db_session.add(RecipeAdditive(recipe_id=new.id, additive_id=additive.id, dosage_pct=0.5, layer_index=0))
    db_session.commit()
    db_session.refresh(old)
    db_session.refresh(new)

    diff = diff_recipe_compositions(old, new)
    additive_changes = [d for d in diff if d["tur"] == "katki_maddesi_dozaji_degisti"]
    assert len(additive_changes) == 1
    assert additive_changes[0]["eski_deger"] == 0.2
    assert additive_changes[0]["yeni_deger"] == 0.5


# --- causal_chain_for_recipe --------------------------------------------

def test_causal_chain_root_has_no_diff(db_session):
    virgin, _ = _polymer_and_materials(db_session)
    recipe = _recipe_with_layer(db_session, virgin)

    chain = causal_chain_for_recipe(db_session, recipe)

    assert len(chain) == 1
    assert chain[0]["diff_from_previous"] is None
    assert chain[0]["physical_test_summary"] == {"basarili": 0, "basarisiz": 0, "beklemede": 0}


def test_causal_chain_reflects_real_revision_as_honest_no_change(db_session):
    """Bugünkü GERÇEK akış (submit_physical_tests): revizyon ebeveynden
    birebir kopyalanır -- zincir bunu dürüstçe boş bir diff (None DEĞİL,
    GERÇEKTEN karşılaştırıldı ve fark bulunamadı: []) olarak göstermeli."""
    virgin, _ = _polymer_and_materials(db_session)
    line = ProductionLine(name="Test Hat", layer_structure="A", layer_count=1, min_micron=10, max_micron=1000, supported_packaging_types=[])
    db_session.add(line)
    db_session.flush()
    recipe = _recipe_with_layer(db_session, virgin)
    recipe.line_id = line.id
    order = ProductionOrder(recipe_id=recipe.id, line_id=line.id, status="tamamlandi", scheduled_qty_units=1000)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    submit_physical_tests(
        db_session, order,
        [{"test_type": "kalinlik", "value": 40.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None}],
    )
    db_session.refresh(recipe)
    new_version = db_session.query(Recipe).filter_by(parent_recipe_id=recipe.id).one()

    chain = causal_chain_for_recipe(db_session, new_version)

    assert len(chain) == 2
    assert chain[0]["diff_from_previous"] is None
    assert chain[1]["diff_from_previous"] == []  # gerçekten karşılaştırıldı, fark yok
    assert chain[1]["status"] == "taslak_optimizasyona_geri_dondu"
    assert chain[0]["physical_test_summary"]["basarisiz"] == 1


def test_causal_chain_includes_real_fire_energy_from_live_data(db_session):
    virgin, _ = _polymer_and_materials(db_session)
    line = ProductionLine(name="Test Hat", layer_structure="A", layer_count=1, min_micron=10, max_micron=1000, supported_packaging_types=[])
    db_session.add(line)
    db_session.flush()
    recipe = _recipe_with_layer(db_session, virgin)
    recipe.line_id = line.id
    order = ProductionOrder(recipe_id=recipe.id, line_id=line.id, status="tamamlandi", scheduled_qty_units=1000)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    simulate_live_data(db_session, order, ticks=2)

    chain = causal_chain_for_recipe(db_session, recipe)

    assert chain[0]["gerceklesen_fire_kg"] is not None
    assert chain[0]["gerceklesen_enerji_kwh"] is not None
    assert chain[0]["line_name"] == "Test Hat"


def test_causal_chain_fire_energy_none_without_production(db_session):
    virgin, _ = _polymer_and_materials(db_session)
    recipe = _recipe_with_layer(db_session, virgin)

    chain = causal_chain_for_recipe(db_session, recipe)

    assert chain[0]["gerceklesen_fire_kg"] is None
    assert chain[0]["gerceklesen_enerji_kwh"] is None


# --- change_outcome_stats -----------------------------------------------

def test_change_outcome_stats_classifies_real_composition_change(db_session):
    virgin, pcr = _polymer_and_materials(db_session)
    parent = _recipe_with_layer(db_session, virgin, ratio_pct=100.0)
    child = Recipe(
        packaging_request_id=parent.packaging_request_id, version=2, source="sistem_uretti",
        status="dogrulandi", is_verified=True, total_micron=70.0, parent_recipe_id=parent.id,
    )
    db_session.add(child)
    db_session.flush()
    db_session.add(RecipeLayer(recipe_id=child.id, layer_index=0, layer_label="A", material_id=virgin.id, ratio_pct=75.0, thickness_micron=70.0))
    db_session.add(RecipeLayer(recipe_id=child.id, layer_index=0, layer_label="A", material_id=pcr.id, ratio_pct=25.0, thickness_micron=70.0))
    db_session.commit()

    stats = change_outcome_stats(db_session)

    assert "malzeme_orani_degisimi" in stats
    assert stats["malzeme_orani_degisimi"]["basarili"] == 1


def test_change_outcome_stats_buckets_real_clone_revision_as_no_change(db_session):
    virgin, _ = _polymer_and_materials(db_session)
    line = ProductionLine(name="Test Hat", layer_structure="A", layer_count=1, min_micron=10, max_micron=1000, supported_packaging_types=[])
    db_session.add(line)
    db_session.flush()
    recipe = _recipe_with_layer(db_session, virgin)
    order = ProductionOrder(recipe_id=recipe.id, line_id=line.id, status="tamamlandi", scheduled_qty_units=1000)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    submit_physical_tests(
        db_session, order,
        [{"test_type": "kalinlik", "value": 40.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None}],
    )

    stats = change_outcome_stats(db_session)

    assert "degisiklik_yok" in stats
    assert stats["degisiklik_yok"]["revizyon_gerekti"] == 1
