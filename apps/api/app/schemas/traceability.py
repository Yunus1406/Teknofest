"""Faz B.9 — Firma Hafızası Zinciri sorgusunun yanıt şeması. Tek bir salt
okunur GET; bkz. app/services/traceability_service.py."""
from pydantic import BaseModel


class TraceabilityCompanyOut(BaseModel):
    id: str
    name: str


class TraceabilityFacilityOut(BaseModel):
    id: str
    name: str
    address: str | None = None


class TraceabilityMachineOut(BaseModel):
    id: str
    name: str
    process_type: str | None = None


class TraceabilitySkuOut(BaseModel):
    id: str
    sku_code: str
    product_name: str


class TraceabilityPackagingRequestOut(BaseModel):
    id: str
    packaging_type: str
    product: str


class TraceabilityRecipeOut(BaseModel):
    id: str
    version: int
    status: str
    is_verified: bool
    total_micron: float | None = None
    total_gsm: float | None = None


class TraceabilityMaterialOut(BaseModel):
    id: str
    name: str
    material_type: str


class TraceabilityCarbonEfOut(BaseModel):
    id: str
    ef_value: float
    unit: str
    is_demo_placeholder: bool
    source: str
    version: str | None = None


class TraceabilityLayerOut(BaseModel):
    layer_index: int
    layer_label: str
    ratio_pct: float
    thickness_micron: float
    material: TraceabilityMaterialOut | None = None
    carbon_ef: TraceabilityCarbonEfOut | None = None


class TraceabilityWasteRecordOut(BaseModel):
    waste_type: str
    kg: float
    recoverable: bool


class TraceabilityProductionOrderOut(BaseModel):
    id: str
    status: str
    scheduled_qty_units: int
    operator: str | None = None
    waste_records: list[TraceabilityWasteRecordOut] = []


class TraceabilityPhysicalTestOut(BaseModel):
    test_type: str
    value: float
    unit: str
    # Faz D.2 — basarili/basarisiz/beklemede. `passed` sadece geriye dönük
    # uyumluluk için tutulur, ASLA tek başına Geçti/Kaldı metni üretmek için
    # kullanılmamalı (beklemede durumunda da False'dur).
    result: str = "beklemede"
    passed: bool


class TraceabilityRegulatoryAssessmentOut(BaseModel):
    regulation_code: str | None = None
    verdict: str
    reasoning: str


class RecipeTraceabilityOut(BaseModel):
    recipe_id: str
    company: TraceabilityCompanyOut | None = None
    facility: TraceabilityFacilityOut | None = None
    machine: TraceabilityMachineOut | None = None
    sku: TraceabilitySkuOut | None = None
    packaging_request: TraceabilityPackagingRequestOut | None = None
    recipe: TraceabilityRecipeOut
    layers: list[TraceabilityLayerOut] = []
    production_orders: list[TraceabilityProductionOrderOut] = []
    physical_tests: list[TraceabilityPhysicalTestOut] = []
    regulatory_assessments: list[TraceabilityRegulatoryAssessmentOut] = []


# Faz O.1 (Madde 18) — Ambalajın Dijital İkizi. `traceability` mevcut
# `RecipeTraceabilityOut`'un AYNISI (Reçete+Katman+Makine+Test+Mevzuat);
# burada sadece Proses/Sürdürülebilirlik/Versiyon Zinciri EKLENİR. Gevşek
# `dict`/`list[dict]` tipler bilinçli -- `schemas/dashboard.py::FinalResultOut.
# per_1000_units: dict` emsaliyle aynı, iç şekli değişebilecek serbest bir
# hesaplanmış görünüm için sıkı bir şema zorlamak gereksiz katılık katar.
class DigitalTwinOut(BaseModel):
    traceability: RecipeTraceabilityOut
    process_parameters: list[dict] = []
    sustainability_per_1000_units: dict | None = None
    version_history: list[dict] = []
