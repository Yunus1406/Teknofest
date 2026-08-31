from pydantic import BaseModel, ConfigDict


class ProductionLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    facility_id: str | None = None
    name: str
    process_type: str | None = None
    layer_structure: str
    layer_count: int
    extruder_count: int | None = None
    min_micron: float
    max_micron: float
    min_gsm: float | None = None
    max_gsm: float | None = None
    max_width_mm: float | None = None
    min_dosage_pct: float | None = None
    max_dosage_pct: float | None = None
    line_speed_m_min: float
    supported_packaging_types: list[str]
    energy_kwh_per_kg: float
    active: bool
    plc_enabled: bool
    opc_ua_enabled: bool
    modbus_tcp_enabled: bool
    api_enabled: bool


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str


class FacilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    company_id: str
    name: str
    address: str | None = None


class LineMatchOut(BaseModel):
    """Dashboard 4 çıktısı: bir hat + o hatta uygun hammaddeler."""

    line: ProductionLineOut
    compatible_material_ids: list[str]
    match_reason: str
