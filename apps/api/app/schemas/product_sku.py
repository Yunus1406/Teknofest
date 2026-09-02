from pydantic import BaseModel, ConfigDict

from app.schemas.traceability import RecipeTraceabilityOut


class ProductSkuCreate(BaseModel):
    sku_code: str
    product_name: str
    packaging_type: str
    usage_area: str
    customer: str | None = None
    customer_sector: str | None = None
    target_market: str
    food_contact: bool = False
    dimensions: dict = {}
    film_thickness_micron: float | None = None
    gsm: float | None = None
    layer_count: int | None = None
    layer_structure: str | None = None
    line_id: str | None = None
    technical_spec_ref: str | None = None
    physical_test_criteria: dict = {}


class ProductSkuUpdate(BaseModel):
    sku_code: str | None = None
    product_name: str | None = None
    packaging_type: str | None = None
    usage_area: str | None = None
    customer: str | None = None
    customer_sector: str | None = None
    target_market: str | None = None
    food_contact: bool | None = None
    dimensions: dict | None = None
    film_thickness_micron: float | None = None
    gsm: float | None = None
    layer_count: int | None = None
    layer_structure: str | None = None
    line_id: str | None = None
    technical_spec_ref: str | None = None
    physical_test_criteria: dict | None = None


class ProductSkuOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sku_code: str
    product_name: str
    packaging_type: str
    usage_area: str
    customer: str | None = None
    customer_sector: str | None = None
    target_market: str
    food_contact: bool
    dimensions: dict
    film_thickness_micron: float | None = None
    gsm: float | None = None
    layer_count: int | None = None
    layer_structure: str | None = None
    line_id: str | None = None
    current_recipe_id: str | None = None
    technical_spec_ref: str | None = None
    physical_test_criteria: dict


class ProductSkuDetailOut(ProductSkuOut):
    """`traceability` yalnızca `current_recipe_id` set edilmişse dolu olur —
    hiç doğrulanmış reçetesi olmayan bir SKU için `None` döner (bkz.
    app/services/traceability_service.py, Faz B.9); bu bir hata durumu
    DEĞİLDİR, sadece henüz üretim geçmişi olmadığı anlamına gelir."""

    traceability: RecipeTraceabilityOut | None = None


# Faz R.2 (Madde 27) — Dijital Uygunluk Dosyası (bkz.
# app/services/compliance_dossier_service.py). `durum`: "tamam"|"kismi"|"eksik".
class ComplianceDossierItemOut(BaseModel):
    key: str
    title: str
    durum: str
    aciklama: str


class ComplianceDossierOut(BaseModel):
    sku_id: str
    sku_code: str
    items: list[ComplianceDossierItemOut]
