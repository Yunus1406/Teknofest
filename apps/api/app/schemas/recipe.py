from pydantic import BaseModel, ConfigDict


class PackagingRequestCreate(BaseModel):
    packaging_type: str
    usage_area: str
    product: str
    target_market: str
    food_contact: bool = False
    target_volume_units: int = 0
    dimensions: dict = {}
    sku_id: str | None = None
    # Bu case var olan bir Ürün/SKU'yu mu hedefliyor (bkz. app/models/product_sku.py)?
    # None ise tek seferlik/deneysel bir talep.
    # Faz G.1 — Aşama 2'nin "Çıkarılan Bilgileri Kontrol Edin" ekranının
    # gösterdiği ek alanlar (hepsi opsiyonel, uydurma değer yok).
    target_thickness_micron: float | None = None
    target_gsm: float | None = None
    physical_performance_notes: str | None = None


class PackagingRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    packaging_type: str
    usage_area: str
    product: str
    target_market: str
    food_contact: bool
    target_volume_units: int
    dimensions: dict
    target_thickness_micron: float | None = None
    target_gsm: float | None = None
    physical_performance_notes: str | None = None
    spec_file_name: str | None = None
    extracted_fields: dict
    status: str
    sku_id: str | None = None


class SpecExtractionOut(BaseModel):
    """Şartname yükleme sonucu — kullanıcı sadece düşük güvenli alanları kontrol eder."""

    packaging_type: str | None = None
    usage_area: str | None = None
    product: str | None = None
    target_market: str | None = None
    food_contact: bool | None = None
    target_volume_units: int | None = None
    dimensions: dict = {}
    target_thickness_micron: float | None = None
    target_gsm: float | None = None
    physical_performance_notes: str | None = None
    field_confidence: dict[str, str] = {}


class RegulatoryAssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    regulation_id: str
    verdict: str
    reasoning: str
    # Faz F.9 — SADECE PPWR Md.6 (geri dönüştürülebilirlik) değerlendirmesinde
    # dolu, diğer maddelerde None. verdict/reasoning DEĞİŞMEDİ.
    recyclability_breakdown: dict | None = None
    # Faz L.1 — "Bu kural neden uygulanıyor?" paneli için yapılandırılmış
    # karar izi (bkz. packaging_service._build_decision_trail).
    decision_trail: dict | None = None
    # Faz L.3 — bu değerlendirme anında dondurulan RegulationRequirement.version.
    regulation_version_snapshot: str | None = None


class EvidenceChecklistItemOut(BaseModel):
    """Faz L.2 — gıda teması kanıt yönetim listesindeki tek bir satır."""

    evidence_type: str
    regulation_ref: str | None
    status: str  # "mevcut" | "eksik" | "gerekli_degil"
    notes: str


class RegulatoryAssessmentSummaryOut(BaseModel):
    overall_verdict: str  # RegulatoryVerdict
    assessments: list[RegulatoryAssessmentOut]
    # Faz L.2 (Madde 4) — sadece food_contact=True iken dolu, değilse [].
    evidence_checklist: list[EvidenceChecklistItemOut] = []


class RecipeLayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    layer_index: int
    layer_label: str
    material_id: str
    ratio_pct: float
    thickness_micron: float


class RecipeAdditiveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    additive_id: str
    dosage_pct: float
    layer_index: int | None = None


class RecipeEvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tier: str
    verdict: str
    reason_code: str
    reason_text: str
    data_confidence: str | None = None


class RecipeMetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    metric_type: str
    value: float
    unit: str
    is_estimated: bool
    data_source_type: str


class RecipeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    packaging_request_id: str
    version: int
    parent_recipe_id: str | None = None
    line_id: str | None = None
    source: str
    status: str
    is_verified: bool
    total_gsm: float | None = None
    total_micron: float | None = None
    # Faz G.4 — firma hafızası taramasının kanıtı: {tier, evidence_count,
    # candidate_recipe_ids}. Referans bulunamadıysa (virgin-only üretim) None.
    reference_search_evidence: dict | None = None
    # Faz G.5 — bu reçetenin GERÇEKTEN beslendiği veri kaynakları (birden
    # fazla olabilir). Sabit 8 değerli kelime dağarcığı, bkz.
    # app/models/recipe.py Recipe.data_source_tags modül yorumu.
    data_source_tags: list[str] | None = None
    layers: list[RecipeLayerOut] = []
    additives: list[RecipeAdditiveOut] = []
    evaluations: list[RecipeEvaluationOut] = []
    metrics: list[RecipeMetricOut] = []
