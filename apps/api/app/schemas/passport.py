"""Faz C.2 — Dijital Ürün Pasaportu yanıt şeması. `public` her zaman dolu;
`authorized` sadece router doğru `dpp_authorized_key`'i doğruladığında
dolar, aksi halde `None` (sessizce — sızıntı yok). Bkz.
app/services/passport_service.py."""
from pydantic import BaseModel

from app.schemas.traceability import RecipeTraceabilityOut


class PassportHeaderOut(BaseModel):
    passport_no: str
    revision: int
    sku_code: str | None = None
    product_name: str | None = None
    recipe_id: str
    recipe_version: int
    facility_name: str | None = None
    company_name: str | None = None
    production_date: str | None = None
    line_name: str | None = None
    packaging_type: str | None = None
    target_market: str | None = None
    # Faz L.4 (Madde 17)
    regulatory_assessment_date: str | None = None
    regulation_versions_used: list[str] = []
    last_checked_date: str | None = None
    affected_by_recent_change: bool = False


class PassportStatusSummaryOut(BaseModel):
    digital_identity: str
    recipe_status: str
    physical_performance: str
    data_traceability: str
    ppwr_status: str
    last_updated: str


class PassportMaterialSummaryOut(BaseModel):
    total_gsm: float | None = None
    total_micron: float | None = None
    layer_count: int
    layer_structure: str | None = None
    polymers: list[str] = []
    virgin_pct: float
    pcr_pct: float
    regranule_pct: float


class PassportEnvironmentalOut(BaseModel):
    per_1000_units: dict | None = None
    gains_pct: dict | None = None
    has_reference: bool
    # Faz I.1 — Bölüm D: Referans|Tahmini|Gerçekleşen (H.4'ün
    # TripleComparisonOut'uyla AYNI şekil, bkz. app/schemas/dashboard.py).
    triple_comparison: dict | None = None


class PassportCircularityOut(BaseModel):
    """Faz I.1 — Bölüm C (Döngüsellik). İkisi de gerçekten yoksa None --
    uydurulmaz."""

    recyclability_breakdown: dict | None = None
    pcr_trend: dict | None = None


class PassportPhysicalTestOut(BaseModel):
    test_type: str
    value: float
    unit: str
    target_min: float | None = None
    target_max: float | None = None
    test_method: str | None = None
    # Faz D.2 — basarili/basarisiz/beklemede.
    result: str = "beklemede"
    passed: bool


class PassportRegulatoryItemOut(BaseModel):
    regulation_code: str | None = None
    article: str | None = None
    verdict: str


class PassportVersionOut(BaseModel):
    id: str
    version: int
    status: str
    is_verified: bool
    created_at: str


# Faz S.1 (Madde 29) — bkz. app/services/recycling_guidance_service.py.
class PassportRecyclingGuidanceOut(BaseModel):
    malzeme_aciklamasi: str
    kutu_talimati: str
    yerel_yonlendirme: str
    aciklama: str


class PassportPublicOut(BaseModel):
    header: PassportHeaderOut
    status_summary: PassportStatusSummaryOut
    material_summary: PassportMaterialSummaryOut
    environmental: PassportEnvironmentalOut
    # Faz I.1 — Bölüm C.
    circularity: PassportCircularityOut
    # Faz I.1 — Bölüm F: ticari bir bilgi değil, ambalajın kullanım
    # amacına dair temel bir gerçek -- public kalır.
    food_contact: bool | None = None
    physical_tests: list[PassportPhysicalTestOut] = []
    regulatory: list[PassportRegulatoryItemOut] = []
    regulatory_disclaimer: str
    version_history: list[PassportVersionOut] = []
    # Faz O.2 (Madde 19) — Sürdürülebilirlik Karnesi özeti: sadece
    # key/label/deger/birim/durum_metni (karşılaştırma yüzdesi ve veri
    # güveni detayı YOK -- bkz. app/services/scorecard_service.py).
    sustainability_scorecard_summary: list[dict] = []
    # Faz S.1 (Madde 29) — tüketiciye yönelik sade geri dönüşüm rehberi.
    geri_donusum_rehberi: PassportRecyclingGuidanceOut


class PassportLayerMaterialDetailOut(BaseModel):
    layer_index: int
    layer_label: str
    material_name: str | None = None
    material_type: str | None = None
    manufacturer: str | None = None
    supplier: str | None = None
    lot_number: str | None = None
    certification_status: str | None = None
    ratio_pct: float


class PassportAdditiveOut(BaseModel):
    """Faz I.1 — Bölüm B: katkı maddesi/masterbatch dozajı, ticari detay
    olduğu için authorized altında."""

    layer_index: int | None = None
    additive_name: str | None = None
    additive_type: str | None = None
    manufacturer: str | None = None
    dosage_pct: float


class PassportRegulatoryReasoningOut(BaseModel):
    regulation_code: str | None = None
    reasoning: str


class PassportAuthorizedOut(BaseModel):
    layer_materials: list[PassportLayerMaterialDetailOut] = []
    additives: list[PassportAdditiveOut] = []
    traceability: RecipeTraceabilityOut
    regulatory_reasoning: list[PassportRegulatoryReasoningOut] = []
    # Faz I.1 — Bölüm G: Faz G.4'ün firma hafızası tarama kanıtı (varsa).
    reference_search_evidence: dict | None = None
    # Faz I.3 — Bölüm G: V1→V2→V3 zincirinin nedensel halkaları (bkz.
    # app/schemas/learning_memory.py CausalChainNodeOut, burada gevşek
    # dict olarak taşınır -- ayrı bir endpoint zaten tam tipli).
    causal_chain: list[dict] = []
    # Faz O.2 (Madde 19) — Sürdürülebilirlik Karnesi'nin tam detayı
    # (karşılaştırma yüzdesi + veri güveni kind'i dahil 9 boyut).
    sustainability_scorecard: list[dict] = []
    # Faz T.1e (Madde 31) — additive. `risk_skoru`: Faz Q.1/R.3, gevşek
    # dict (RiskScoreOut ile aynı şekil). `kanit_tamamlanma_orani`: Faz
    # R.2, SKU yoksa None (uydurulmaz). `sektore_gore_konum`: Faz N.2.
    risk_skoru: dict | None = None
    kanit_tamamlanma_orani: dict | None = None
    sektore_gore_konum: dict | None = None


class DigitalProductPassportOut(BaseModel):
    public: PassportPublicOut
    authorized: PassportAuthorizedOut | None = None
    qr_code_data_uri: str
