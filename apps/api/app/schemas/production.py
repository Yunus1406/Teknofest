from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductionOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    recipe_id: str
    line_id: str
    status: str
    scheduled_qty_units: int
    # Faz B.6 — simülasyon tamamlanana kadar hepsi None kalır.
    operator: str | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    downtime_minutes: float | None = None
    avg_micron: float | None = None
    actual_layer_ratios: dict = {}


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


class SustainabilityResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    per_1000_units: dict
    is_actual: bool
