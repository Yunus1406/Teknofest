"""Kısıt kuralları. Her kural fonksiyonu bir `RecipeCandidate` + `EvaluationContext`
alır, eleme gerektiren bir durum varsa `EvaluationResult` döner, yoksa None.

Üç kategori:
  - Kesin Teknik Kısıt: fiziksel/hat kapasitesiyle çelişen, tartışmasız elenir.
  - Malzeme-Proses Kısıtı: malzeme uyumluluğu, gıda teması, mevzuat (PPWR/FCM)
    kaynaklı elenir.
Tahmini Fiziksel Performans katmanı burada değil, optimization/scorer.py'de
puanlanır (elemek değil, sıralamak için)."""
from app.constraint_engine.types import (
    EvaluationContext,
    EvaluationResult,
    EvaluationTier,
    EvaluationVerdict,
    RecipeCandidate,
)

# Faz Q.2 (Madde 25) — geçmişte AYNI hatta denenip fiziksel testi başarısız
# olmuş bir kombinasyona (aynı malzeme kümesi + kalınlık ±%5) ne kadar
# yakın olursa, o kombinasyonun tekrar başarısız olma riski o kadar yüksek
# kabul edilir -- bu bir "kesin teknik kısıt" değil, geçmiş KANITA dayalı
# bir tahmin, bu yüzden Tahmini Fiziksel Performans katmanında.
_FAILED_RECIPE_THICKNESS_TOLERANCE_PCT = 5.0

# Bilinen, birlikte geri dönüştürülmesi zor / uyumsuz polimer çiftleri
# (PPWR Md.6 — geri dönüştürülebilirlik tasarımı bağlamında).
INCOMPATIBLE_POLYMER_PAIRS: set[frozenset[str]] = {
    frozenset({"PET", "PE"}),
    frozenset({"PET", "PP"}),
    frozenset({"PS", "PET"}),
    frozenset({"PLA", "PET"}),
    frozenset({"PLA", "PE"}),
}


# --- Kesin Teknik Kısıt --------------------------------------------------

def rule_micron_within_line_range(
    candidate: RecipeCandidate, ctx: EvaluationContext
) -> EvaluationResult | None:
    total = candidate.total_micron
    if total < ctx.line.min_micron or total > ctx.line.max_micron:
        return EvaluationResult(
            tier=EvaluationTier.KESIN_TEKNIK_KISIT,
            verdict=EvaluationVerdict.ELENDI,
            reason_code="micron_disi",
            reason_text=(
                f"Toplam kalınlık {total:.1f} mikron, '{ctx.line.name}' hattının "
                f"üretebildiği {ctx.line.min_micron:.0f}-{ctx.line.max_micron:.0f} "
                "mikron aralığının dışında."
            ),
        )
    return None


def rule_layer_count_match(
    candidate: RecipeCandidate, ctx: EvaluationContext
) -> EvaluationResult | None:
    distinct_layers = len({l.layer_index for l in candidate.layers})
    if distinct_layers != ctx.line.layer_count:
        return EvaluationResult(
            tier=EvaluationTier.KESIN_TEKNIK_KISIT,
            verdict=EvaluationVerdict.ELENDI,
            reason_code="katman_sayisi_uyumsuz",
            reason_text=(
                f"Reçete {distinct_layers} katmanlı, ancak '{ctx.line.name}' hattı "
                f"({ctx.line.layer_structure}) {ctx.line.layer_count} katman üretecek "
                "şekilde kurulu."
            ),
        )
    return None


def _slug(text: str) -> str:
    """Kısıt motoru bağımsız/saf kalsın diye app.services.common.slugify'nin
    küçük, tekrarlanan bir kopyası — yalnızca ambalaj türü karşılaştırması
    için (ör. 'plastik tabak' ~ 'plastik_tabak')."""
    return text.strip().lower().replace(" ", "_").replace("ı", "i")


def rule_packaging_type_supported(
    candidate: RecipeCandidate, ctx: EvaluationContext
) -> EvaluationResult | None:
    supported_slugs = {_slug(t) for t in ctx.line.supported_packaging_types}
    if _slug(ctx.packaging.packaging_type) not in supported_slugs:
        return EvaluationResult(
            tier=EvaluationTier.KESIN_TEKNIK_KISIT,
            verdict=EvaluationVerdict.ELENDI,
            reason_code="ambalaj_turu_desteklenmiyor",
            reason_text=(
                f"'{ctx.line.name}' hattı '{ctx.packaging.packaging_type}' ambalaj "
                "türünü üretecek şekilde tanımlı değil."
            ),
        )
    return None


# --- Malzeme-Proses Kısıtı -----------------------------------------------

def rule_material_line_compatibility(
    candidate: RecipeCandidate, ctx: EvaluationContext
) -> EvaluationResult | None:
    for layer in candidate.layers:
        max_ratio = ctx.line.material_max_ratio.get(layer.material.id)
        if max_ratio is None:
            return EvaluationResult(
                tier=EvaluationTier.MALZEME_PROSES_KISITI,
                verdict=EvaluationVerdict.ELENDI,
                reason_code="hat_malzeme_eslesmiyor",
                reason_text=(
                    f"'{layer.material.name}', '{ctx.line.name}' hattında tanımlı "
                    "işlenebilir hammaddeler arasında değil."
                ),
            )
        if layer.ratio_pct > max_ratio:
            return EvaluationResult(
                tier=EvaluationTier.MALZEME_PROSES_KISITI,
                verdict=EvaluationVerdict.ELENDI,
                reason_code="hat_malzeme_orani_asildi",
                reason_text=(
                    f"'{layer.material.name}' için {layer.ratio_pct:.0f}% oranı, "
                    f"'{ctx.line.name}' hattının izin verdiği azami {max_ratio:.0f}%'i "
                    "aşıyor."
                ),
            )
    return None


def rule_material_own_max_ratio(
    candidate: RecipeCandidate, ctx: EvaluationContext
) -> EvaluationResult | None:
    for layer in candidate.layers:
        cap = layer.material.max_recommended_ratio_pct
        if layer.ratio_pct > cap:
            return EvaluationResult(
                tier=EvaluationTier.MALZEME_PROSES_KISITI,
                verdict=EvaluationVerdict.ELENDI,
                reason_code="malzeme_kendi_oran_siniri_asildi",
                reason_text=(
                    f"'{layer.material.name}' bu içerik seviyesinde (degradasyon "
                    f"katsayısı {layer.material.degradation_factor:.2f}) güvenle "
                    f"azami {cap:.0f}% oranında önerilir; talep edilen {layer.ratio_pct:.0f}%."
                ),
            )
    return None


def rule_food_contact_layer_eligibility(
    candidate: RecipeCandidate, ctx: EvaluationContext
) -> EvaluationResult | None:
    """Gıda temaslı iç katmanın sertifikasyon uygunluğu — bu, EU 1935/2004
    çerçeve tüzüğünün (gıda ile temas eden malzemeler) konusudur. PPWR Md.7
    ayrı bir mesele: geri dönüştürülmüş İÇERİK ORANI zorunluluğu (bkz.
    scorer._regulatory_margin_score) — bu ikisi metinde KARIŞTIRILMAMALI.
    Ayrıca PCR (post-tüketici) ile PIR/regranül (dahili fire) ayrı sınıflar
    olduğundan, gerekçe metninde malzemenin hangisi olduğu açıkça belirtilir."""
    if not ctx.packaging.food_contact:
        return None
    for contact in candidate.contact_layers:
        if not contact.material.food_contact_eligible:
            material_kind = {
                "pcr": "PCR (post-tüketici geri dönüştürülmüş)",
                "regranul": "PIR-Regranül (dahili/pre-consumer fire geri kazanım)",
                "virgin": "virgin",
            }.get(contact.material.material_type, contact.material.material_type)
            return EvaluationResult(
                tier=EvaluationTier.MALZEME_PROSES_KISITI,
                verdict=EvaluationVerdict.ELENDI,
                reason_code="gida_temasi_uygun_degil",
                reason_text=(
                    f"Gıda temaslı ambalajda iç katman '{contact.material.name}' ({material_kind}) "
                    "gıda sınıfı sertifikasyonuna sahip değil (EU 1935/2004 çerçeve tüzüğü)."
                ),
            )
    return None


def rule_additive_dosage_and_food_contact(
    candidate: RecipeCandidate, ctx: EvaluationContext
) -> EvaluationResult | None:
    for usage in candidate.additives:
        a = usage.additive
        if usage.dosage_pct < a.dosage_min_pct or usage.dosage_pct > a.dosage_max_pct:
            return EvaluationResult(
                tier=EvaluationTier.MALZEME_PROSES_KISITI,
                verdict=EvaluationVerdict.ELENDI,
                reason_code="katki_dozaj_disi",
                reason_text=(
                    f"'{a.name}' dozajı {usage.dosage_pct:.2f}%, önerilen "
                    f"{a.dosage_min_pct:.2f}-{a.dosage_max_pct:.2f}% aralığının dışında."
                ),
            )
        if ctx.packaging.food_contact and not a.food_contact_eligible:
            return EvaluationResult(
                tier=EvaluationTier.MALZEME_PROSES_KISITI,
                verdict=EvaluationVerdict.ELENDI,
                reason_code="katki_gida_temasi_uygun_degil",
                reason_text=(
                    f"'{a.name}' gıda temaslı ambalajlarda kullanım için "
                    "sertifikalı değil."
                ),
            )
    return None


def rule_ppwr_recyclability_multi_material(
    candidate: RecipeCandidate, ctx: EvaluationContext
) -> EvaluationResult | None:
    polymer_codes = {l.material.polymer_code for l in candidate.layers}
    if len(polymer_codes) <= 1:
        return None
    for pair in INCOMPATIBLE_POLYMER_PAIRS:
        if pair.issubset(polymer_codes):
            a, b = tuple(pair)
            return EvaluationResult(
                tier=EvaluationTier.MALZEME_PROSES_KISITI,
                verdict=EvaluationVerdict.ELENDI,
                reason_code="uyumsuz_cok_polimer_yapisi",
                reason_text=(
                    f"Katmanlarda birlikte bulunan {a}/{b} kombinasyonu, standart "
                    "geri dönüşüm akışında ayrıştırılamıyor (PPWR Md.6 — geri "
                    "dönüştürülebilirlik tasarımı gerekliliğiyle çelişiyor)."
                ),
            )
    return None


# --- Faz Q.2 (Madde 25): Başarısız Reçete Geçmişine Benzerlik ------------

def rule_similar_to_failed_history(
    candidate: RecipeCandidate, ctx: EvaluationContext
) -> EvaluationResult | None:
    if not ctx.failed_recipe_signatures:
        return None
    candidate_material_ids = frozenset(l.material.id for l in candidate.layers)
    for sig in ctx.failed_recipe_signatures:
        if candidate_material_ids != sig.material_ids:
            continue
        if sig.total_micron <= 0:
            continue
        sapma_pct = abs(candidate.total_micron - sig.total_micron) / sig.total_micron * 100
        if sapma_pct <= _FAILED_RECIPE_THICKNESS_TOLERANCE_PCT:
            return EvaluationResult(
                tier=EvaluationTier.TAHMINI_FIZIKSEL_PERFORMANS,
                verdict=EvaluationVerdict.ELENDI,
                reason_code="gecmis_basarisizlik",
                reason_text=(
                    f"Bu kombinasyon (aynı hammaddeler, {candidate.total_micron:.0f}µm) "
                    f"reçete {sig.recipe_id[:8]} sürüm {sig.version}'de aynı hatta başarısız "
                    f"olmuştu: {sig.basarisizlik_nedeni}"
                ),
                data_confidence="orta",
            )
    return None


# --- Faz K.7 (Madde 9): Reçete Matematiksel Tutarlılık Kontrolleri --------
# Bu, ELENDİ/GEÇTİ tier'lı bir kural DEĞİL -- "iş kuralı" ihlali değil,
# matematiksel bir İÇ TUTARSIZLIK (üretim mantığında bir hatayı işaret eder,
# ör. 11+49+11=71 gibi katman toplamı hedefle uyuşmayan bir reçete). Bu
# yüzden ayrı bir fonksiyon: reçete PERSIST edilmeden önce çağrılır, boş
# olmayan bir liste dönerse reçete HİÇ üretim zincirine giremez.
def validate_recipe_math_consistency(
    candidate: RecipeCandidate,
    target_total_micron: float | None,
    tolerance_micron: float = 0.5,
    tolerance_pct: float = 0.5,
) -> list[str]:
    failures: list[str] = []

    # (1) Katman kalınlıkları toplamı = toplam ambalaj kalınlığı.
    if target_total_micron is not None:
        diff = abs(candidate.total_micron - target_total_micron)
        if diff > tolerance_micron:
            failures.append(
                f"Katman kalınlıkları toplamı {candidate.total_micron:.1f} µm, hedef "
                f"{target_total_micron:.1f} µm ile eşleşmiyor (fark {diff:.1f} µm)."
            )

    # (2) Her katmanın İÇİNDEKİ malzeme oranları toplamı = %100 (blend'ler
    # dahil -- aynı layer_index'i paylaşan birden fazla malzeme satırı olabilir).
    by_index: dict[int, float] = {}
    for layer in candidate.layers:
        by_index[layer.layer_index] = by_index.get(layer.layer_index, 0.0) + layer.ratio_pct
    for idx, total in sorted(by_index.items()):
        if abs(total - 100.0) > tolerance_pct:
            failures.append(f"{idx}. katman içindeki malzeme oranları toplamı %{total:.1f}, %100 olmalı.")

    # (3) Virgin+PCR+PIR ağırlıklı kompozisyon toplamı = %100 (reçete geneli).
    composition_total = sum(candidate.weighted_composition_pct().values())
    if abs(composition_total - 100.0) > tolerance_pct:
        failures.append(f"Virgin+PCR+PIR ağırlıklı kompozisyon toplamı %{composition_total:.1f}, %100 olmalı.")

    return failures


# --- Faz M.2 (Madde 12): Eleme Nedenlerinin Kategorik Dağılımı ------------
# Huni görselleştirmesinin yanında "180 malzeme uyumsuzluğu, 74 mevzuat, 40
# makine kısıtı" gibi bir özet üretmek için her reason_code'u 3 kullanıcı
# dostu kategoriye eşler. Yeni bir kural eklendiğinde buraya da bir satır
# eklenmesi gerekir (aksi halde o kod "diger" kategorisine düşer, sessizce
# kaybolmaz).
REASON_CODE_CATEGORIES: dict[str, str] = {
    "micron_disi": "makine_hat_kisiti",
    "katman_sayisi_uyumsuz": "makine_hat_kisiti",
    "ambalaj_turu_desteklenmiyor": "makine_hat_kisiti",
    "hat_malzeme_eslesmiyor": "malzeme_uyumsuzlugu",
    "hat_malzeme_orani_asildi": "malzeme_uyumsuzlugu",
    "malzeme_kendi_oran_siniri_asildi": "malzeme_uyumsuzlugu",
    "katki_dozaj_disi": "malzeme_uyumsuzlugu",
    "gida_temasi_uygun_degil": "mevzuat",
    "katki_gida_temasi_uygun_degil": "mevzuat",
    "uyumsuz_cok_polimer_yapisi": "mevzuat",
    # Faz Q.2 (Madde 25) — kendi kategorisi (mevcut 4'ten AYRI, "diger"ye
    # düşürülmez ki kullanıcı bu somut, kanıta dayalı nedeni net görsün).
    "gecmis_basarisizlik": "gecmis_basarisizlik",
}


def categorize_eliminations(
    eliminated: list[tuple[RecipeCandidate, list[EvaluationResult]]],
) -> dict[str, int]:
    """Faz M.2 — TÜM elenen adaylar için (sadece `notable_eliminated`'in
    tuttuğu 3 örnek DEĞİL) her adayın İLK ihlali (ALL_RULES sırasındaki ilk
    eşleşen kural, `evaluate_candidate`'ın kısayoldan çıkmadan topladığı
    `violations` listesinin ilk elemanı) o adayın kategorisini belirler --
    bir aday BAŞINA tek kategori sayılır (ihlal başına değil), aksi halde
    toplam elenen aday sayısını aşar ve yanıltıcı olurdu (kullanıcının
    örneğindeki "294 eleme: 180+74+40" toplamı elenen sayısına eşittir)."""
    counts: dict[str, int] = {
        "malzeme_uyumsuzlugu": 0, "mevzuat": 0, "makine_hat_kisiti": 0,
        "gecmis_basarisizlik": 0, "diger": 0,
    }
    for _candidate, violations in eliminated:
        if not violations:
            continue
        category = REASON_CODE_CATEGORIES.get(violations[0].reason_code, "diger")
        counts[category] += 1
    return counts


ALL_RULES = [
    rule_micron_within_line_range,
    rule_layer_count_match,
    rule_packaging_type_supported,
    rule_material_line_compatibility,
    rule_material_own_max_ratio,
    rule_food_contact_layer_eligibility,
    rule_additive_dosage_and_food_contact,
    rule_ppwr_recyclability_multi_material,
    rule_similar_to_failed_history,
]
