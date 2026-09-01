"""Faz K.7 (Madde 9) — 450 µm hedeflenen bir ürün için 11+49+11=71 µm gibi
matematiksel olarak tutarsız bir reçete üretilebiliyordu; sistem reçeteyi
kabul etmeden önce (1) katman kalınlıkları toplamı=hedef, (2) katman
oranları toplamı=%100, (3) virgin+PCR+PIR toplamı=%100 kontrollerini hiç
yapmıyordu. Ayrıca Aşama 6 optimizasyonun aday üretimi de (K.2'nin Akıllı
Başlangıç'taki eşleniği) hedef kalınlığı hiç okumuyor, hattın min/max
ortasını kullanıyordu -- bu dosya hem pure-function kontrolleri hem bu ikinci
kök nedeni ayrı ayrı üretir/kilitler."""
from app.constraint_engine.rules import validate_recipe_math_consistency
from app.constraint_engine.types import LayerCandidate, MaterialSpec, RecipeCandidate
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest
from app.optimization.candidate_generator import LayerMaterialOptions, generate_candidates
from app.services import optimization_service


def _material_spec(id_, material_type="virgin"):
    return MaterialSpec(
        id=id_, name=id_, polymer_code="PE", material_type=material_type,
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, degradation_factor=0.0,
        mfi_g_10min=None, cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8,
    )


# --- validate_recipe_math_consistency (saf fonksiyon) ----------------------

def test_consistent_candidate_has_no_failures():
    virgin = _material_spec("v1")
    candidate = RecipeCandidate(layers=[
        LayerCandidate(layer_index=0, layer_label="A", material=virgin, ratio_pct=100.0, thickness_micron=150.0),
        LayerCandidate(layer_index=1, layer_label="B", material=virgin, ratio_pct=100.0, thickness_micron=150.0),
    ])
    assert validate_recipe_math_consistency(candidate, target_total_micron=300.0) == []


def test_thickness_mismatch_is_reported():
    """11+49+11=71 senaryosunun birebir eşleniği: katman toplamı hedeften
    (450) sapıyor."""
    virgin = _material_spec("v1")
    candidate = RecipeCandidate(layers=[
        LayerCandidate(layer_index=0, layer_label="A", material=virgin, ratio_pct=100.0, thickness_micron=11.0),
        LayerCandidate(layer_index=1, layer_label="B", material=virgin, ratio_pct=100.0, thickness_micron=49.0),
        LayerCandidate(layer_index=2, layer_label="A", material=virgin, ratio_pct=100.0, thickness_micron=11.0),
    ])
    failures = validate_recipe_math_consistency(candidate, target_total_micron=450.0)
    assert any("Katman kalınlıkları toplamı" in f for f in failures)


def test_layer_ratio_not_summing_to_100_is_reported():
    virgin = _material_spec("v1", "virgin")
    pcr = _material_spec("p1", "pcr")
    # Aynı layer_index (0) içinde iki malzeme -- toplamı 90, %100 DEĞİL.
    candidate = RecipeCandidate(layers=[
        LayerCandidate(layer_index=0, layer_label="A", material=virgin, ratio_pct=70.0, thickness_micron=100.0),
        LayerCandidate(layer_index=0, layer_label="A", material=pcr, ratio_pct=20.0, thickness_micron=100.0),
    ])
    failures = validate_recipe_math_consistency(candidate, target_total_micron=100.0)
    assert any("katman içindeki malzeme oranları toplamı" in f for f in failures)


# --- generate_candidates artık target_total_micron'u gerçekten kullanıyor --

def test_generate_candidates_uses_target_thickness_when_given():
    virgin = _material_spec("v1")
    line_options = [LayerMaterialOptions(layer_label=lbl, virgin=virgin, recycled_options=[]) for lbl in ["A", "B", "A"]]
    from app.constraint_engine.types import LineSpec
    line = LineSpec(
        id="l1", name="Test", layer_structure="A/B/A", layer_count=3, min_micron=50, max_micron=90,
        min_gsm=None, max_gsm=None, supported_packaging_types=[], material_max_ratio={},
    )

    candidates = generate_candidates(line, line_options, ratio_step_pct=10, target_total_micron=450.0)
    assert len(candidates) > 0
    for c in candidates:
        assert abs(c.total_micron - 450.0) < 0.01, "Hedef kalınlık verildiğinde hattın ortası (70) DEĞİL, hedef (450) kullanılmalı"


def test_generate_candidates_falls_back_to_line_midpoint_when_no_target():
    virgin = _material_spec("v1")
    line_options = [LayerMaterialOptions(layer_label=lbl, virgin=virgin, recycled_options=[]) for lbl in ["A", "B", "A"]]
    from app.constraint_engine.types import LineSpec
    line = LineSpec(
        id="l1", name="Test", layer_structure="A/B/A", layer_count=3, min_micron=50, max_micron=90,
        min_gsm=None, max_gsm=None, supported_packaging_types=[], material_max_ratio={},
    )

    candidates = generate_candidates(line, line_options, ratio_step_pct=10)
    assert candidates[0].total_micron == 70.0


# --- run_optimization ucuna kadar: finalist gerçekten hedefi yansıtıyor ----

def test_run_optimization_finalists_use_target_thickness_not_line_midpoint(db_session):
    db = db_session
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    virgin = Material(
        polymer_id=polymer.id, name="PE Virgin K7", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(virgin)
    db.flush()
    line = ProductionLine(
        name="Test Hat K7", layer_structure="A/B/A", layer_count=3, min_micron=50, max_micron=90,
        supported_packaging_types=["esnek_film_ambalaj"],
    )
    db.add(line)
    db.flush()
    db.add(LineMaterialCompatibility(line_id=line.id, material_id=virgin.id, max_ratio_pct=100.0))
    db.commit()

    # Hedef (80 µm), hattın ortasından (70 µm) BİLEREK farklı -- ama hala
    # hattın 50-90 aralığı İÇİNDE (K.4'ün mikron kriterinin geçmesi için).
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test k7", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
        target_thickness_micron=80.0,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    db.refresh(line)

    result = optimization_service.run_optimization(db, req.id, line.id, ratio_step_pct=10)
    assert len(result["finalist_candidate_ids"]) > 0

    from app.models.optimization import OptimizationCandidate
    finalist = db.get(OptimizationCandidate, result["finalist_candidate_ids"][0])
    assert finalist.recipe.total_micron == 80.0, "Finalist, hattın ortası (70) DEĞİL Aşama 2'nin hedefini (80) yansıtmalı"
