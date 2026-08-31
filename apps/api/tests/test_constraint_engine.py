"""Kısıt motoru birim testleri — deterministik, DB/LLM bağımlılığı yok."""
from app.constraint_engine.engine import evaluate_candidate
from app.constraint_engine.types import (
    EvaluationContext,
    LayerCandidate,
    LineSpec,
    MaterialSpec,
    PackagingContext,
    RecipeCandidate,
)

VIRGIN_PP = MaterialSpec(
    id="m-virgin-pp", name="PP Virgin", polymer_code="PP", material_type="virgin",
    food_contact_eligible=True, max_recommended_ratio_pct=100, degradation_factor=0.0,
    mfi_g_10min=12, cost_per_kg=38, carbon_factor_kg_co2_per_kg=1.9,
)
PCR_PP_FOOD_GRADE = MaterialSpec(
    id="m-pcr-pp", name="PP PCR Gıda Sınıfı", polymer_code="PP", material_type="pcr",
    food_contact_eligible=True, max_recommended_ratio_pct=50, degradation_factor=0.08,
    mfi_g_10min=10, cost_per_kg=30, carbon_factor_kg_co2_per_kg=0.6,
)
REGRANUL_PP_NON_FOOD = MaterialSpec(
    id="m-regranul-pp", name="PP Regranül", polymer_code="PP", material_type="regranul",
    food_contact_eligible=False, max_recommended_ratio_pct=30, degradation_factor=0.15,
    mfi_g_10min=14, cost_per_kg=24, carbon_factor_kg_co2_per_kg=0.5,
)
VIRGIN_PET = MaterialSpec(
    id="m-virgin-pet", name="PET Virgin", polymer_code="PET", material_type="virgin",
    food_contact_eligible=True, max_recommended_ratio_pct=100, degradation_factor=0.0,
    mfi_g_10min=None, cost_per_kg=45, carbon_factor_kg_co2_per_kg=2.3,
)

LINE = LineSpec(
    id="line-1", name="Hat-1", layer_structure="A/B/A", layer_count=3,
    min_micron=300, max_micron=900, min_gsm=None, max_gsm=None,
    supported_packaging_types=["plastik_tabak"],
    material_max_ratio={
        VIRGIN_PP.id: 100, PCR_PP_FOOD_GRADE.id: 50, REGRANUL_PP_NON_FOOD.id: 30, VIRGIN_PET.id: 100,
    },
)

FOOD_CONTACT_CTX = EvaluationContext(
    packaging=PackagingContext(packaging_type="plastik tabak", food_contact=True, target_volume_units=1000),
    line=LINE,
    regulations=[],
)


def _three_layer_all_virgin() -> RecipeCandidate:
    return RecipeCandidate(
        layers=[
            LayerCandidate(0, "A", VIRGIN_PP, 100.0, 90.0),
            LayerCandidate(1, "B", VIRGIN_PP, 100.0, 420.0),
            LayerCandidate(2, "A", VIRGIN_PP, 100.0, 90.0),
        ]
    )


def test_fully_virgin_candidate_passes():
    result = evaluate_candidate(_three_layer_all_virgin(), FOOD_CONTACT_CTX)
    assert result.passed
    assert result.violations == []


def test_micron_out_of_range_is_eliminated():
    candidate = RecipeCandidate(
        layers=[
            LayerCandidate(0, "A", VIRGIN_PP, 100.0, 10.0),
            LayerCandidate(1, "B", VIRGIN_PP, 100.0, 10.0),
            LayerCandidate(2, "A", VIRGIN_PP, 100.0, 10.0),
        ]
    )  # toplam 30 mikron, hat aralığı 300-900
    result = evaluate_candidate(candidate, FOOD_CONTACT_CTX)
    assert not result.passed
    assert any(v.reason_code == "micron_disi" for v in result.violations)


def test_non_food_grade_material_in_contact_layer_is_eliminated():
    candidate = RecipeCandidate(
        layers=[
            LayerCandidate(0, "A", VIRGIN_PP, 100.0, 90.0),
            LayerCandidate(1, "B", VIRGIN_PP, 100.0, 420.0),
            LayerCandidate(2, "A", VIRGIN_PP, 80.0, 90.0),
            LayerCandidate(2, "A", REGRANUL_PP_NON_FOOD, 20.0, 90.0),
        ]
    )
    result = evaluate_candidate(candidate, FOOD_CONTACT_CTX)
    assert not result.passed
    violation = next(v for v in result.violations if v.reason_code == "gida_temasi_uygun_degil")
    assert all(v.tier == "malzeme_proses_kisiti" for v in result.violations)
    # PIR-regranül açıkça adlandırılmalı; PPWR Md.7 (içerik oranı) ile
    # karıştırılmamalı -- bu kural EU 1935/2004 (FCM) sertifikasyonuyla ilgili.
    assert "PIR-Regranül" in violation.reason_text
    assert "Md.7" not in violation.reason_text
    assert "1935/2004" in violation.reason_text


def test_same_non_food_grade_material_ok_when_not_food_contact():
    non_food_ctx = EvaluationContext(
        packaging=PackagingContext(packaging_type="plastik tabak", food_contact=False, target_volume_units=1000),
        line=LINE,
        regulations=[],
    )
    candidate = RecipeCandidate(
        layers=[
            LayerCandidate(0, "A", VIRGIN_PP, 100.0, 90.0),
            LayerCandidate(1, "B", VIRGIN_PP, 100.0, 420.0),
            LayerCandidate(2, "A", VIRGIN_PP, 80.0, 90.0),
            LayerCandidate(2, "A", REGRANUL_PP_NON_FOOD, 20.0, 90.0),
        ]
    )
    result = evaluate_candidate(candidate, non_food_ctx)
    assert result.passed


def test_incompatible_multi_polymer_structure_is_eliminated():
    candidate = RecipeCandidate(
        layers=[
            LayerCandidate(0, "A", VIRGIN_PET, 100.0, 90.0),
            LayerCandidate(1, "B", VIRGIN_PP, 100.0, 420.0),
            LayerCandidate(2, "A", VIRGIN_PET, 100.0, 90.0),
        ]
    )
    result = evaluate_candidate(candidate, FOOD_CONTACT_CTX)
    assert not result.passed
    assert any(v.reason_code == "uyumsuz_cok_polimer_yapisi" for v in result.violations)


def test_ratio_above_material_own_ceiling_is_eliminated():
    candidate = RecipeCandidate(
        layers=[
            LayerCandidate(0, "A", VIRGIN_PP, 50.0, 90.0),
            LayerCandidate(0, "A", REGRANUL_PP_NON_FOOD, 50.0, 90.0),  # malzemenin kendi tavanı %30
            LayerCandidate(1, "B", VIRGIN_PP, 100.0, 420.0),
            LayerCandidate(2, "A", VIRGIN_PP, 100.0, 90.0),
        ]
    )
    result = evaluate_candidate(candidate, FOOD_CONTACT_CTX)
    assert not result.passed
    assert any(v.reason_code == "malzeme_kendi_oran_siniri_asildi" for v in result.violations)
