"""Tahmini Fiziksel Performans skorlayıcısı için birim testleri."""
from app.constraint_engine.types import (
    DataConfidence,
    LayerCandidate,
    MaterialSpec,
    RecipeCandidate,
    RegulationSpec,
)
from app.optimization.scorer import score_candidate

VIRGIN_PP = MaterialSpec(
    id="m-virgin-pp", name="PP Virgin", polymer_code="PP", material_type="virgin",
    food_contact_eligible=True, max_recommended_ratio_pct=100, degradation_factor=0.0,
    mfi_g_10min=12, cost_per_kg=38, carbon_factor_kg_co2_per_kg=1.9,
)
PCR_PP = MaterialSpec(
    id="m-pcr-pp", name="PP PCR", polymer_code="PP", material_type="pcr",
    food_contact_eligible=True, max_recommended_ratio_pct=50, degradation_factor=0.08,
    mfi_g_10min=10, cost_per_kg=30, carbon_factor_kg_co2_per_kg=0.6,
)
REGRANUL_PP = MaterialSpec(
    id="m-regranul-pp", name="PP Regranül", polymer_code="PP", material_type="regranul",
    food_contact_eligible=False, max_recommended_ratio_pct=30, degradation_factor=0.15,
    mfi_g_10min=14, cost_per_kg=24, carbon_factor_kg_co2_per_kg=0.5,
)


def _all_virgin() -> RecipeCandidate:
    return RecipeCandidate(
        layers=[
            LayerCandidate(0, "A", VIRGIN_PP, 100.0, 90.0),
            LayerCandidate(1, "B", VIRGIN_PP, 100.0, 420.0),
            LayerCandidate(2, "A", VIRGIN_PP, 100.0, 90.0),
        ]
    )


def _high_recycled_core() -> RecipeCandidate:
    return RecipeCandidate(
        layers=[
            LayerCandidate(0, "A", VIRGIN_PP, 100.0, 90.0),
            LayerCandidate(1, "B", VIRGIN_PP, 30.0, 420.0),
            LayerCandidate(1, "B", REGRANUL_PP, 30.0, 420.0),
            LayerCandidate(1, "B", PCR_PP, 40.0, 420.0),
            LayerCandidate(2, "A", VIRGIN_PP, 100.0, 90.0),
        ]
    )


def test_score_is_within_unit_interval():
    for candidate in (_all_virgin(), _high_recycled_core()):
        result = score_candidate(candidate, regulations=[])
        assert 0.0 <= result.total <= 1.0
        for v in result.breakdown.values():
            assert 0.0 <= v <= 1.0


def test_all_virgin_candidate_has_high_confidence():
    result = score_candidate(_all_virgin(), regulations=[])
    assert result.data_confidence == DataConfidence.YUKSEK


def test_high_recycled_content_has_low_confidence_and_is_disclosed():
    """Geçmiş üretim verisi yokken yüksek geri dönüşüm oranlı reçeteler
    dürüstçe düşük veri güveniyle etiketlenmeli — asla 'Yüksek' olmamalı."""
    result = score_candidate(_high_recycled_core(), regulations=[])
    assert result.data_confidence in (DataConfidence.ORTA, DataConfidence.DUSUK)
    assert result.data_confidence != DataConfidence.YUKSEK


def test_recycled_content_reduces_estimated_carbon_vs_virgin_baseline():
    result = score_candidate(_high_recycled_core(), regulations=[])
    assert result.estimated_carbon_kg_co2_per_kg < result.virgin_baseline_carbon_kg_co2_per_kg


# --- PPWR Md.7: PIR/regranül, geri dönüştürülmüş içerik hesabına dahil değil ---

ART7_FOOD_CONTACT_PET_DISI = RegulationSpec(
    code="PPWR-ART-7",
    title="Geri Dönüştürülmüş İçerik Zorunlulukları (PPWR Md.7)",
    category="geri_donusturulmus_icerik",
    criteria={
        "pir_excluded_from_calculation": True,
        "targets": [
            {"category": "gida_temasli_pet_disi_plastik", "food_contact": True, "pet": False, "by_year": {"2030": 10, "2040": 25}}
        ],
    },
    applicable_packaging_types=["plastik_tabak"],
)


def _candidate_with_recycled(material_type: str, pct: float) -> RecipeCandidate:
    recycled = PCR_PP if material_type == "pcr" else REGRANUL_PP
    return RecipeCandidate(
        layers=[
            LayerCandidate(0, "A", VIRGIN_PP, 100.0 - pct, 90.0),
            LayerCandidate(0, "A", recycled, pct, 90.0),
        ]
    )


def test_pir_regranul_does_not_count_toward_ppwr_art7_margin():
    """Aynı oranda (%20) geri dönüşüm içeriği kullanan iki aday: biri PCR
    (post-tüketici), diğeri PIR-regranül (dahili fire). PPWR Md.7 marjı
    yalnızca PCR'ı saydığından, PIR adayının marj skoru PCR adayınınkinden
    daha düşük (ya da en fazla eşit, asla daha yüksek) olmalı."""
    pcr_candidate = _candidate_with_recycled("pcr", 20.0)
    pir_candidate = _candidate_with_recycled("regranul", 20.0)

    pcr_result = score_candidate(pcr_candidate, regulations=[ART7_FOOD_CONTACT_PET_DISI], food_contact=True)
    pir_result = score_candidate(pir_candidate, regulations=[ART7_FOOD_CONTACT_PET_DISI], food_contact=True)

    assert pcr_result.breakdown["mevzuat_marji"] > pir_result.breakdown["mevzuat_marji"]
    # PIR hiç PCR içermiyor -> marj katkısı sıfır tabana yakın olmalı.
    assert pir_result.breakdown["mevzuat_marji"] == 0.0


def test_carbon_ef_status_defaults_to_undefined_when_not_specified():
    """MaterialSpec'i doğrudan (ORM'siz) oluşturan eski testler carbon_ef_status
    geçmez -- dürüstçe 'tanimlanmadi' varsayılana düşmeli, asla 'kaynaklı EF'
    gibi görünmemeli."""
    result = score_candidate(_all_virgin(), regulations=[])
    assert result.carbon_ef_status == "tanimlanmadi"


def test_carbon_ef_status_reflects_worst_case_across_layers():
    from app.services.carbon import TANIMLI_DEMO, TANIMLI_GERCEK

    virgin_demo = MaterialSpec(
        id="m-v-demo", name="PP Virgin (demo EF)", polymer_code="PP", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100, degradation_factor=0.0,
        mfi_g_10min=12, cost_per_kg=38, carbon_factor_kg_co2_per_kg=1.9,
        carbon_ef_status=TANIMLI_GERCEK,
    )
    core_demo = MaterialSpec(
        id="m-c-demo", name="PP Core (demo EF)", polymer_code="PP", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100, degradation_factor=0.0,
        mfi_g_10min=12, cost_per_kg=38, carbon_factor_kg_co2_per_kg=1.9,
        carbon_ef_status=TANIMLI_DEMO,
    )
    candidate = RecipeCandidate(
        layers=[
            LayerCandidate(0, "A", virgin_demo, 100.0, 90.0),
            LayerCandidate(1, "B", core_demo, 100.0, 420.0),
            LayerCandidate(2, "A", virgin_demo, 100.0, 90.0),
        ]
    )
    result = score_candidate(candidate, regulations=[])
    # bir katman bile 'demo' ise, tüm reçetenin karbon güveni 'demo'ya düşer
    assert result.carbon_ef_status == TANIMLI_DEMO


def test_undefined_category_does_not_fabricate_a_target():
    """Tabloda kaydı olmayan bir kategori (ör. PET, gıda temaslı olmayan)
    için sabit bir yüzde uydurulmamalı; nötr (1.0) skor dönmeli."""
    pet_material = MaterialSpec(
        id="m-virgin-pet", name="PET Virgin", polymer_code="PET", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100, degradation_factor=0.0,
        mfi_g_10min=None, cost_per_kg=45, carbon_factor_kg_co2_per_kg=2.3,
    )
    candidate = RecipeCandidate(layers=[LayerCandidate(0, "A", pet_material, 100.0, 90.0)])

    result = score_candidate(candidate, regulations=[ART7_FOOD_CONTACT_PET_DISI], food_contact=True)
    assert result.breakdown["mevzuat_marji"] == 1.0
