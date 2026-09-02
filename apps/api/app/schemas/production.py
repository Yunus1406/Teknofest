from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.dashboard import LayerCompositionOut


class ProductionOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    recipe_id: str
    line_id: str
    status: str
    scheduled_qty_units: int
    # Faz H.2 — üretim emrini oluşturma anında dolar (operatör onayı olmadan
    # emir oluşturulamaz, bkz. production_flow_service.create_production_order).
    order_no: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    # Faz B.6 — simülasyon tamamlanana kadar hepsi None kalır.
    operator: str | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    downtime_minutes: float | None = None
    avg_micron: float | None = None
    actual_layer_ratios: dict = {}


class OrderAdditiveOut(BaseModel):
    layer_index: int | None
    additive_id: str
    additive_name: str
    dosage_pct: float


class ProcessParameterSuggestionOut(BaseModel):
    """Faz F.7 kütüphanesinden, hattın `process_type`'ıyla eşleşen TİPİK
    parametre aralığı — bir ÖNERİDİR, otomatik bir hedef/kabul kriteri
    DEĞİLDİR (bkz. SuggestedTestTargetOut'un aynı disiplini)."""

    parameter_name: str
    typical_min: float | None
    typical_max: float | None
    unit: str
    source: str | None


class ProductionOrderSummaryOut(BaseModel):
    """Faz H.2 — Aşama 9'un gerçek bir üretim talimatına dönüşmesi: reçete
    kodu+versiyon, toplam kalınlık, katman dağılımı+hammadde oranları
    (RecipeLayer/RecipeAdditive, Faz B'den — yeniden hesaplanmaz, doğrudan
    okunur), hedef hat hızı, hedef proses parametresi önerisi. Hat
    eşleşmemişse veya F.7 kütüphanesinde o proses tipi için satır yoksa
    ilgili alanlar boş/None kalır — ASLA uydurulmaz."""

    order_no: str | None
    recipe_code: str
    recipe_version: int
    total_micron: float | None
    layers: list[LayerCompositionOut]
    additives: list[OrderAdditiveOut]
    target_line_speed_m_min: float | None
    target_process_parameters: list[ProcessParameterSuggestionOut]
    approved_by: str | None
    approved_at: datetime | None


class WasteRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    ts: datetime | None = None
    waste_type: str
    kg: float
    recoverable: bool


class ProductionLiveDataOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ts: str | None = None
    produced_qty_units: int  # kümülatif
    period_produced_qty_units: int  # dönemsel (bu satırdaki üretim)
    material_consumption: dict
    line_speed_m_min: float
    energy_kwh: float  # dönemsel
    cumulative_energy_kwh: float
    waste_kg: float  # dönemsel
    cumulative_waste_kg: float
    source: str


class PhysicalTestIn(BaseModel):
    test_type: str
    value: float
    unit: str
    target_min: float | None = None
    target_max: float | None = None
    test_method: str | None = None


class PhysicalTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    test_type: str
    value: float
    unit: str
    target_min: float | None = None
    target_max: float | None = None
    test_method: str | None = None
    # Faz D.2 — asıl doğruluk kaynağı: basarili/basarisiz/beklemede.
    # `passed` geriye dönük uyumluluk için tutulur (result=='basarili' ise
    # True) — UI 'Geçti'/'Kaldı' metnini ASLA sadece `passed`tan üretmemeli,
    # `result`u kullanmalı (aksi halde 'beklemede' yanlışlıkla 'Kaldı' gibi
    # okunabilir).
    result: str = "beklemede"
    passed: bool
    source: str


class PhysicalVerificationSubmit(BaseModel):
    production_order_id: str
    tests: list[PhysicalTestIn]


class SuggestedTestTargetOut(BaseModel):
    test_type: str
    unit: str
    test_method: str
    nominal_value: float | None
    target_min: float | None
    target_max: float | None
    note: str
    # Faz F.6 — ayrı, açıkça "öneri" etiketli alan; target_min/target_max
    # DEĞİLDİR, otomatik bir geçme/kalma kriterine dönüşmez.
    suggested_min: float | None = None
    suggested_max: float | None = None
    suggestion_source: str | None = None
    # Mekanik Test Kabul Kriterleri — "hesaplanan" (kalınlık/gramaj) /
    # "kullanici_girisi" (Aşama 2'de girilen gerçek kriter) / None.
    target_source: str | None = None


class SustainabilityResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    per_1000_units: dict
    is_actual: bool
