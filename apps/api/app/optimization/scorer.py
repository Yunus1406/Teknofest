"""Tahmini Fiziksel Performans katmanı: kısıt motorundan geçen adaylar
üzerinde çok amaçlı ağırlıklı skor. Geçmiş üretim/laboratuvar verisi henüz
olmadığından, skor malzeme bilgi tabanındaki (degradasyon katsayısı, karbon
faktörü, maliyet) mühendislik tahminlerine dayanır — bu yüzden veri güveni
dürüstçe Orta/Düşük olarak etiketlenir; Yüksek yalnızca tamamen virgin
(bilinen/kanıtlanmış) kompozisyonlarda verilir."""
from dataclasses import dataclass

from app.constraint_engine.types import DataConfidence, RegulationSpec, RecipeCandidate
from app.services.carbon import TANIMLANMADI, worst_status
from app.services.common import find_pcr_target_category, recipe_is_pet_dominant

DEFAULT_WEIGHTS: dict[str, float] = {
    "teknik_performans": 0.30,
    "uretilebilirlik": 0.20,
    "mevzuat_marji": 0.15,
    "karbon": 0.15,
    "fire_riski": 0.10,
    "maliyet": 0.10,
}

# rPET/gıda sınıfı PCR haricindeki tüm geri dönüşüm malzemelerinde referans
# alınan azami "sektörde denenmiş" oran — bunun üstü konservatif olarak
# düşük veri güveni alır.
_HIGH_CONFIDENCE_RECYCLED_CEILING_PCT = 15.0


@dataclass
class ScoreResult:
    total: float  # 0-1
    breakdown: dict[str, float]
    data_confidence: str
    estimated_carbon_kg_co2_per_kg: float
    estimated_cost_per_kg: float
    virgin_baseline_carbon_kg_co2_per_kg: float
    virgin_baseline_cost_per_kg: float
    # Bu adaydaki en az güvenilir karbon EF durumu (bkz. app/services/carbon.py)
    # -- "tanimli_demo"/"tanimlanmadi" ise UI'da "DEMO/VARSAYIMSAL EF" ya da
    # "EF TANIMLANMADI" etiketi gösterilmeli; asla kaynaklı bir EF gibi sunulmaz.
    carbon_ef_status: str = TANIMLANMADI


def _weighted_avg(candidate: RecipeCandidate, attr: str) -> float:
    total_micron = candidate.total_micron or 1.0
    acc = 0.0
    for layer in candidate.layers:
        layer_weight = layer.thickness_micron / total_micron
        material_share = layer.ratio_pct / 100.0
        acc += layer_weight * material_share * getattr(layer.material, attr)
    return acc


def _virgin_baseline(candidate: RecipeCandidate, attr: str) -> float:
    """Aynı katman yapısının tamamen virgin ile üretilmiş halinin değeri —
    kazanım kıyaslaması (Dashboard 8) için referans."""
    total_micron = candidate.total_micron or 1.0
    by_index_virgin_value: dict[int, float] = {}
    for layer in candidate.layers:
        if layer.material.material_type == "virgin":
            by_index_virgin_value[layer.layer_index] = getattr(layer.material, attr)
    if not by_index_virgin_value:
        return _weighted_avg(candidate, attr)
    weights = _thickness_weight_by_index(candidate)
    return sum(
        weights.get(idx, 0.0) * val for idx, val in by_index_virgin_value.items()
    )


def _thickness_weight_by_index(candidate: RecipeCandidate) -> dict[int, float]:
    total_micron = candidate.total_micron or 1.0
    by_index: dict[int, float] = {}
    for layer in candidate.layers:
        by_index[layer.layer_index] = layer.thickness_micron
    return {idx: t / total_micron for idx, t in by_index.items()}


def _technical_performance_score(candidate: RecipeCandidate) -> float:
    avg_degradation = _weighted_avg(candidate, "degradation_factor")
    return max(0.0, 1.0 - avg_degradation)


def _producibility_score(candidate: RecipeCandidate) -> float:
    """Kullanılan geri dönüşüm oranının, malzemenin/hattın izin verdiği
    tavana ne kadar yaklaştığını ölçer — tavana yakın oranlar üretilebilirlik
    riskini artırır."""
    risks = []
    for layer in candidate.layers:
        cap = layer.material.max_recommended_ratio_pct or 100.0
        risks.append(layer.ratio_pct / cap if cap > 0 else 0.0)
    if not risks:
        return 1.0
    avg_risk = sum(risks) / len(risks)
    return max(0.0, 1.0 - 0.6 * avg_risk)


def _regulatory_margin_score(
    candidate: RecipeCandidate, regulations: list[RegulationSpec], food_contact: bool
) -> float:
    """PPWR Md.7 marjı YALNIZCA post-tüketici PCR'a göre hesaplanır — PIR/
    regranül (dahili fire) bu hesaba dahil edilmez (bkz. Md.7 kriterinin
    `pir_excluded_from_calculation` bayrağı). Hedef, kategori/tarih tablosundan
    (regulations.yaml) okunur; bizim demo kapsamımız dışında bir kategori
    (ör. PET) için tabloda kayıt yoksa, sabit bir yüzde UYDURULMAZ — nötr
    (1.0) skor döner ve bu durum `data_confidence`'a yansımaz çünkü mevzuat
    marjı zaten yalnızca bir skor bileşenidir, bir kısıt motoru elemesi değil."""
    composition = candidate.weighted_composition_pct()
    recycled_pct = composition.get("pcr", 0.0)  # PIR/regranül HARİÇ

    polymer_codes = [l.material.polymer_code for l in candidate.layers]
    is_pet = recipe_is_pet_dominant(polymer_codes)

    target: float | None = None
    for reg in regulations:
        if reg.code == "PPWR-ART-7":
            entry = find_pcr_target_category(reg.criteria, food_contact, is_pet)
            if entry:
                target = entry.get("by_year", {}).get("2030")
            break

    if target is None or target <= 0:
        return 1.0
    return min(1.2, recycled_pct / target) / 1.2 if recycled_pct < target else 1.0


def _waste_risk_score(candidate: RecipeCandidate) -> float:
    """Fire riski proxy'si: yüksek degradasyonlu / çok bileşenli reçeteler
    işlem sırasında daha fazla fire riski taşır (mühendislik tahmini)."""
    avg_degradation = _weighted_avg(candidate, "degradation_factor")
    material_count = len({l.material.id for l in candidate.layers})
    complexity_penalty = min(0.3, 0.05 * max(0, material_count - 2))
    return max(0.0, 1.0 - avg_degradation - complexity_penalty)


def _cost_score(candidate: RecipeCandidate) -> tuple[float, float, float]:
    est_cost = _weighted_avg(candidate, "cost_per_kg")
    baseline_cost = _virgin_baseline(candidate, "cost_per_kg") or est_cost or 1.0
    score = max(0.0, min(1.0, (baseline_cost - est_cost) / baseline_cost + 0.5))
    return score, est_cost, baseline_cost


def _carbon_score(candidate: RecipeCandidate) -> tuple[float, float, float]:
    est_carbon = _weighted_avg(candidate, "carbon_factor_kg_co2_per_kg")
    baseline_carbon = _virgin_baseline(candidate, "carbon_factor_kg_co2_per_kg") or est_carbon or 1.0
    score = max(0.0, min(1.0, (baseline_carbon - est_carbon) / baseline_carbon + 0.5))
    return score, est_carbon, baseline_carbon


def _data_confidence(candidate: RecipeCandidate) -> str:
    composition = candidate.weighted_composition_pct()
    recycled_pct = composition.get("pcr", 0.0) + composition.get("regranul", 0.0)
    if recycled_pct <= 0.01:
        return DataConfidence.YUKSEK
    if recycled_pct <= _HIGH_CONFIDENCE_RECYCLED_CEILING_PCT:
        return DataConfidence.ORTA
    return DataConfidence.DUSUK


def _carbon_ef_status(candidate: RecipeCandidate) -> str:
    return worst_status([layer.material.carbon_ef_status for layer in candidate.layers])


def score_candidate(
    candidate: RecipeCandidate,
    regulations: list[RegulationSpec],
    food_contact: bool = False,
    weights: dict[str, float] | None = None,
) -> ScoreResult:
    w = weights or DEFAULT_WEIGHTS
    carbon_score, est_carbon, baseline_carbon = _carbon_score(candidate)
    cost_score, est_cost, baseline_cost = _cost_score(candidate)

    breakdown = {
        "teknik_performans": _technical_performance_score(candidate),
        "uretilebilirlik": _producibility_score(candidate),
        "mevzuat_marji": _regulatory_margin_score(candidate, regulations, food_contact),
        "karbon": carbon_score,
        "fire_riski": _waste_risk_score(candidate),
        "maliyet": cost_score,
    }
    total = sum(breakdown[k] * w.get(k, 0.0) for k in breakdown)
    return ScoreResult(
        total=round(total, 4),
        breakdown={k: round(v, 4) for k, v in breakdown.items()},
        data_confidence=_data_confidence(candidate),
        estimated_carbon_kg_co2_per_kg=round(est_carbon, 4),
        estimated_cost_per_kg=round(est_cost, 4),
        virgin_baseline_carbon_kg_co2_per_kg=round(baseline_carbon, 4),
        virgin_baseline_cost_per_kg=round(baseline_cost, 4),
        carbon_ef_status=_carbon_ef_status(candidate),
    )
