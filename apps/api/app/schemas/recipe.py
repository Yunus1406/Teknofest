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


class RegulatoryAssessmentSummaryOut(BaseModel):
    overall_verdict: str  # RegulatoryVerdict
    assessments: list[RegulatoryAssessmentOut]


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
    layers: list[RecipeLayerOut] = []
    additives: list[RecipeAdditiveOut] = []
    evaluations: list[RecipeEvaluationOut] = []
    metrics: list[RecipeMetricOut] = []
