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


class PassportPublicOut(BaseModel):
    header: PassportHeaderOut
    status_summary: PassportStatusSummaryOut
    material_summary: PassportMaterialSummaryOut
    environmental: PassportEnvironmentalOut
    physical_tests: list[PassportPhysicalTestOut] = []
    regulatory: list[PassportRegulatoryItemOut] = []
    regulatory_disclaimer: str
    version_history: list[PassportVersionOut] = []


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


class PassportRegulatoryReasoningOut(BaseModel):
    regulation_code: str | None = None
    reasoning: str


class PassportAuthorizedOut(BaseModel):
    layer_materials: list[PassportLayerMaterialDetailOut] = []
    traceability: RecipeTraceabilityOut
    regulatory_reasoning: list[PassportRegulatoryReasoningOut] = []


class DigitalProductPassportOut(BaseModel):
    public: PassportPublicOut
    authorized: PassportAuthorizedOut | None = None
    qr_code_data_uri: str
