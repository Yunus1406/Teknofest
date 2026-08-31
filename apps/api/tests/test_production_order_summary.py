"""Faz H.2 — Aşama 9'un üretim emri zenginleştirmesi: `order_no` +
`approved_by`/`approved_at` (operatör onayı olmadan emir oluşturulamaz),
`build_order_summary`'nin reçete kodu+versiyon, katman/hammadde/dozaj
dağılımı, hedef hat hızı ve Faz F.7 proses parametresi önerisini GERÇEKTEN
mevcut veriden derlediğini (uydurmadığını) doğrulayan testler."""
import pytest

from app.knowledge_base.loader import load_process_references
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Additive, Material, Polymer
from app.models.recipe import PackagingRequest, Recipe, RecipeAdditive, RecipeLayer
from app.services.production_flow_service import build_order_summary, create_production_order


def _seed_recipe_and_line(db_session, process_type="Blown Film Extrusion"):
    load_process_references(db_session)  # F.7 process_reference.yaml

    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()
    material = Material(
        polymer_id=polymer.id, name="LDPE Virgin", material_type="virgin", density_g_cm3=0.92,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=34.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    additive = Additive(
        name="Kayganlaştırıcı", additive_type="slip", dosage_min_pct=0.1, dosage_max_pct=0.5,
        food_contact_eligible=True, cost_per_kg=60.0,
    )
    db_session.add_all([material, additive])
    db_session.flush()

    line = ProductionLine(
        name="Test Ekstrüzyon Hattı", process_type=process_type, layer_structure="A",
        layer_count=1, min_micron=20, max_micron=100, line_speed_m_min=55, active=True,
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
        packaging_request_id=request.id, version=2, source="sistem_uretti", status="onerildi",
        total_micron=70.0, line_id=line.id,
    )
    db_session.add(recipe)
    db_session.flush()
    db_session.add(
        RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0)
    )
    db_session.add(
        RecipeAdditive(recipe_id=recipe.id, additive_id=additive.id, dosage_pct=0.3, layer_index=0)
    )
    db_session.commit()
    db_session.refresh(recipe)
    return recipe, line


def test_create_production_order_requires_approved_by(db_session):
    recipe, line = _seed_recipe_and_line(db_session)
    with pytest.raises(ValueError):
        create_production_order(db_session, recipe, 1000, "")
    with pytest.raises(ValueError):
        create_production_order(db_session, recipe, 1000, "   ")


def test_create_production_order_generates_order_no_and_approval(db_session):
    recipe, line = _seed_recipe_and_line(db_session)
    order = create_production_order(db_session, recipe, 1000, "Op. A. Yıldız")
    assert order.order_no is not None
    assert order.order_no.startswith("UE-")
    assert order.approved_by == "Op. A. Yıldız"
    assert order.approved_at is not None


def test_order_no_sequence_increments(db_session):
    recipe, line = _seed_recipe_and_line(db_session)
    order1 = create_production_order(db_session, recipe, 1000, "Op. A")
    order2 = create_production_order(db_session, recipe, 500, "Op. B")
    assert order1.order_no != order2.order_no
    seq1 = int(order1.order_no.split("-")[-1])
    seq2 = int(order2.order_no.split("-")[-1])
    assert seq2 == seq1 + 1


def test_build_order_summary_includes_recipe_code_layers_and_additives(db_session):
    recipe, line = _seed_recipe_and_line(db_session)
    order = create_production_order(db_session, recipe, 1000, "Op. A")

    summary = build_order_summary(db_session, order)

    assert summary["recipe_code"] == f"{recipe.id[:8]}-V2"
    assert summary["recipe_version"] == 2
    assert summary["total_micron"] == 70.0
    assert len(summary["layers"]) == 1
    assert summary["layers"][0]["materials"][0]["material_name"] == "LDPE Virgin"
    assert len(summary["additives"]) == 1
    assert summary["additives"][0]["additive_name"] == "Kayganlaştırıcı"
    assert summary["additives"][0]["layer_index"] == 0
    assert summary["target_line_speed_m_min"] == 55
    assert summary["approved_by"] == "Op. A"


def test_build_order_summary_process_parameters_matched_from_f7_library(db_session):
    recipe, line = _seed_recipe_and_line(db_session, process_type="Blown Film Extrusion")
    order = create_production_order(db_session, recipe, 1000, "Op. A")

    summary = build_order_summary(db_session, order)

    assert len(summary["target_process_parameters"]) > 0
    names = {p["parameter_name"] for p in summary["target_process_parameters"]}
    assert "melt_temperature_c" in names


def test_build_order_summary_process_parameters_empty_when_no_match_no_fabrication(db_session):
    recipe, line = _seed_recipe_and_line(db_session, process_type="Bilinmeyen Proses Türü XYZ")
    order = create_production_order(db_session, recipe, 1000, "Op. A")

    summary = build_order_summary(db_session, order)

    assert summary["target_process_parameters"] == []
