"""Aday reçete üretimi: hattın katman yapısı + uygun hammaddeler + hedef
kalınlık aralığından, virgin/PCR/regranül oranı taranarak parametrik aday
reçeteler üretir. Optimizasyon motorunun ilk adımı — kısıt motoruna girecek
ham aday havuzunu oluşturur.

Her katman, virgin ile geri dönüşüm malzemesinin (varsa) karışımı olarak
modellenir: aynı layer_index'i paylaşan iki `LayerCandidate` satırı (biri
virgin, biri PCR/regranül), toplamda katmanın %100'ünü oluşturur."""
from dataclasses import dataclass

from app.constraint_engine.types import LayerCandidate, LineSpec, MaterialSpec, RecipeCandidate

# A/B/A gibi simetrik yapılarda tipik kalınlık dağılımı: dış katmanlar ince,
# çekirdek kalın (gıda/ürünle temas etmeyen çekirdek katman genelde geri
# dönüşüm malzemesini taşır — sektörde yaygın mühendislik pratiği).
_LAYER_THICKNESS_WEIGHTS: dict[int, list[float]] = {
    1: [1.0],
    2: [0.5, 0.5],
    3: [0.15, 0.70, 0.15],
    5: [0.10, 0.15, 0.50, 0.15, 0.10],
}

RATIO_STEP_PCT = 10  # geri dönüşüm oranı tarama adımı
# Kombinasyon patlamasını önlemek için malzeme başına üst sınır — Faz D.1
# ÖNCESİNDE bu 5'ti; RATIO_STEP_PCT=10 ile bu, bir malzemenin gerçek
# max_recommended_ratio_pct/hat uyumluluk oranı %50'nin ÜZERİNDE olsa bile
# taramanın her zaman %50'de kesilmesine yol açıyordu (aday sayısı, %50'nin
# üzerindeki hiçbir oran değişikliğine duyarsız kalıyordu — GERÇEK BUG,
# bkz. tests/test_candidate_generation_dynamics.py). 20, tipik
# ratio_step_pct değerlerinde (>=5) 0-100 aralığının TAMAMININ hiç
# kesilmeden taranmasını garanti eder; yine de patolojik derecede küçük bir
# ratio_step_pct (<5) için bir güvenlik sınırı olarak kalır.
MAX_STEPS_PER_MATERIAL = 20


@dataclass
class LayerMaterialOptions:
    """Bir katman pozisyonu (A/B/C harfi) için uygun virgin ve (varsa) geri
    dönüşüm malzemesi adayları — Dashboard 4'ün eşleştirme çıktısından gelir."""

    layer_label: str
    virgin: MaterialSpec
    recycled_options: list[MaterialSpec]  # pcr/regranul, boş olabilir


def thickness_weights_for_layer_count(layer_count: int) -> list[float]:
    """Diğer servisler de (örn. Aşama 5 başlangıç reçetesi) aynı tipik
    katman kalınlık dağılımını kullanabilsin diye dışa açık."""
    return _LAYER_THICKNESS_WEIGHTS.get(layer_count) or [1.0 / layer_count] * layer_count


# Geriye dönük iç kullanım takma adı
_thickness_weights = thickness_weights_for_layer_count


def _layer_content_variants(
    opt: LayerMaterialOptions, line: LineSpec, ratio_step_pct: int
) -> list[list[tuple[MaterialSpec, float]]]:
    """Bir katman için olası içerik varyasyonları: her biri
    [(malzeme, katman_içi_oran), ...] listesi (tek malzeme %100, ya da
    virgin+geri dönüşüm blend'i, toplam %100). Adım sayısı MATERYAL BAŞINA
    sınırlanır — birden fazla geri dönüşüm seçeneği varsa (örn. PCR + regranül)
    her biri kendi payını korur, biri diğerini komple ekarte etmez."""
    variants: list[list[tuple[MaterialSpec, float]]] = [[(opt.virgin, 100.0)]]
    for recycled in opt.recycled_options:
        cap = min(
            recycled.max_recommended_ratio_pct,
            line.material_max_ratio.get(recycled.id, 100.0),
        )
        step = max(ratio_step_pct, 1)
        pct = step
        added = 0
        while pct <= cap and added < MAX_STEPS_PER_MATERIAL:
            variants.append([(opt.virgin, 100.0 - pct), (recycled, float(pct))])
            pct += step
            added += 1
    return variants


def _per_layer_variants(
    line: LineSpec, layer_options: list[LayerMaterialOptions], ratio_step_pct: int
) -> list[list[list[tuple[MaterialSpec, float]]]]:
    """`generate_candidates` VE `describe_candidate_generation` AYNI bu
    fonksiyonu çağırır — aday sayısı ile 'Adaylar Nasıl Oluşturuldu?'
    açıklamasındaki çarpımın birbirinden SAPMASI matematiksel olarak imkansız
    (ikisi de tam olarak bu listenin uzunluklarından türetilir, bkz. Faz D.1)."""
    return [_layer_content_variants(opt, line, ratio_step_pct) for opt in layer_options]


def generate_candidates(
    line: LineSpec,
    layer_options: list[LayerMaterialOptions],
    ratio_step_pct: int = RATIO_STEP_PCT,
) -> list[RecipeCandidate]:
    """`layer_options` hattın katman sayısı kadar (sırayla dıştan içe) girilir.
    Katmanlar birbirinden bağımsız taranıp kartezyen çarpımı alınır."""
    layer_count = len(layer_options)
    weights = _thickness_weights(layer_count)
    target_total_micron = (line.min_micron + line.max_micron) / 2

    per_layer_variants = _per_layer_variants(line, layer_options, ratio_step_pct)

    candidates: list[RecipeCandidate] = []
    for combo in _cartesian(per_layer_variants):
        layers: list[LayerCandidate] = []
        for idx, (content, opt, weight) in enumerate(zip(combo, layer_options, weights)):
            thickness = target_total_micron * weight
            for material, ratio in content:
                layers.append(
                    LayerCandidate(
                        layer_index=idx,
                        layer_label=opt.layer_label,
                        material=material,
                        ratio_pct=ratio,
                        thickness_micron=thickness,
                    )
                )
        candidates.append(RecipeCandidate(layers=layers, additives=[]))
    return candidates


def _cartesian(lists: list[list]) -> list[list]:
    result: list[list] = [[]]
    for lst in lists:
        result = [r + [item] for r in result for item in lst]
    return result


def describe_candidate_generation(
    line: LineSpec, layer_options: list[LayerMaterialOptions], ratio_step_pct: int = RATIO_STEP_PCT
) -> dict:
    """Faz D.1 — 'Adaylar Nasıl Oluşturuldu?' açıklaması. `_per_layer_variants`
    üzerinden `generate_candidates` ile AYNI hesaplamayı paylaşır; kartezyen
    çarpımın matematiksel tanımı gereği (`len(_cartesian(xs)) ==
    prod(len(x) for x in xs)`), buradaki `total` her zaman
    `len(generate_candidates(line, layer_options, ratio_step_pct))` ile
    birebir eşittir — iki ayrı hesap değil, aynı girdiden türetilen tek
    hesap (bkz. tests/test_candidate_generation_dynamics.py)."""
    per_layer_variants = _per_layer_variants(line, layer_options, ratio_step_pct)

    layers_info = []
    total = 1
    for opt, variants in zip(layer_options, per_layer_variants):
        count = len(variants)
        total *= count
        layers_info.append(
            {
                "layer_label": opt.layer_label,
                "virgin_material_name": opt.virgin.name,
                "recycled_material_names": [r.name for r in opt.recycled_options],
                "variant_count": count,
            }
        )

    formula_text = (
        " × ".join(f"Katman {info['layer_label']} ({info['variant_count']} seçenek)" for info in layers_info)
        + f" = {total} benzersiz aday (kısıt motoru öncesi)"
        if layers_info
        else "Hiçbir katman seçeneği üretilemedi."
    )

    return {"layers": layers_info, "total": total, "formula_text": formula_text}
