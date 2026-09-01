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
    # Faz E.2 — Makine Parkı teknik kartı (hepsi opsiyonel, bkz.
    # app/models/infrastructure.py modül docstring'i).
    manufacturer: str | None = None
    model: str | None = None
    install_year: int | None = None
    nominal_capacity_kg_year: float | None = None
    actual_capacity_kg_year: float | None = None
    min_line_speed_m_min: float | None = None
    max_line_speed_m_min: float | None = None
    layer_structure_type: str | None = None
    screw_diameter_mm: float | None = None
    ld_ratio: float | None = None
    suitable_polymer_codes: list[str] = []
    pcr_capable: bool | None = None
    pir_capable: bool | None = None
    max_pcr_technical_pct: float | None = None
    max_pir_technical_pct: float | None = None
    gravimetric_dosing_equipped: bool | None = None
    online_thickness_control: bool | None = None
    energy_metering_equipped: bool | None = None
    average_waste_rate_pct: float | None = None
    availability_status: str | None = None
    # Faz G.3 — bu hat "Kayıtlı Makineden Hat Oluştur" ile birden fazla
    # kayıtlı satırın birleşimi olarak mı tanımlandı? None/[] = hayır.
    component_line_ids: list[str] | None = None


class LineMatchCriteriaOut(BaseModel):
    """Faz K.4 — Aşama 4'ün uygunluk matrisindeki 5 kriter."""

    proses: bool
    malzeme_uyumu: bool
    mikron_araligi: bool
    katman_yapisi: bool
    ambalaj_turu: bool


class LineMatchOut(BaseModel):
    """Dashboard 4 çıktısı: bir hat + o hatta uygun hammaddeler + (Faz K.4)
    uygunluk matrisi/skoru. `eligible=False` olan hatlar da listede kalır —
    ki "uygun hat bulunamadı" derken kullanıcı NEDEN elendiğini görebilsin."""

    line: ProductionLineOut
    compatible_material_ids: list[str]
    match_reason: str
    eligible: bool = True
    score_pct: int = 100
    criteria: LineMatchCriteriaOut | None = None
    missing: list[str] = []
    # Faz N.1b (Madde 14) — "yuksek" (mikron_araligi gerçekten karşılaştırıldı)
    # veya "varsayimsal" (hedef kalınlık girilmemiş, kriter geçti VARSAYILDI).
    mikron_araligi_veri_guveni: str = "yuksek"


class ProductionLineCreate(BaseModel):
    """Faz E.2 — 'Yeni Makine Ekle'. Sadece optimizasyon motorunun ZATEN
    zorunlu tuttuğu alanlar (name/layer_structure/min_micron/max_micron)
    gerçekten zorunlu; geri kalan teknik kart alanlarının hepsi opsiyonel."""

    facility_id: str | None = None
    name: str
    process_type: str | None = None
    layer_structure: str
    layer_count: int = 1
    extruder_count: int | None = None
    min_micron: float
    max_micron: float
    min_gsm: float | None = None
    max_gsm: float | None = None
    max_width_mm: float | None = None
    min_dosage_pct: float | None = None
    max_dosage_pct: float | None = None
    line_speed_m_min: float = 0.0
    supported_packaging_types: list[str] = []
    energy_kwh_per_kg: float = 0.0
    active: bool = True
    plc_enabled: bool = False
    opc_ua_enabled: bool = False
    modbus_tcp_enabled: bool = False
    api_enabled: bool = False
    manufacturer: str | None = None
    model: str | None = None
    install_year: int | None = None
    nominal_capacity_kg_year: float | None = None
    actual_capacity_kg_year: float | None = None
    min_line_speed_m_min: float | None = None
    max_line_speed_m_min: float | None = None
    layer_structure_type: str | None = None
    screw_diameter_mm: float | None = None
    ld_ratio: float | None = None
    suitable_polymer_codes: list[str] = []
    pcr_capable: bool | None = None
    pir_capable: bool | None = None
    max_pcr_technical_pct: float | None = None
    max_pir_technical_pct: float | None = None
    gravimetric_dosing_equipped: bool | None = None
    online_thickness_control: bool | None = None
    energy_metering_equipped: bool | None = None
    average_waste_rate_pct: float | None = None
    availability_status: str | None = None
    component_line_ids: list[str] | None = None


class ProductionLineUpdate(BaseModel):
    """Kısmi güncelleme — sadece gönderilen alanlar değişir (bkz.
    app/api/v1/routers/machine_park.py `exclude_unset=True`)."""

    component_line_ids: list[str] | None = None
    facility_id: str | None = None
    name: str | None = None
    process_type: str | None = None
    layer_structure: str | None = None
    layer_count: int | None = None
    extruder_count: int | None = None
    min_micron: float | None = None
    max_micron: float | None = None
    min_gsm: float | None = None
    max_gsm: float | None = None
    max_width_mm: float | None = None
    min_dosage_pct: float | None = None
    max_dosage_pct: float | None = None
    line_speed_m_min: float | None = None
    supported_packaging_types: list[str] | None = None
    energy_kwh_per_kg: float | None = None
    active: bool | None = None
    plc_enabled: bool | None = None
    opc_ua_enabled: bool | None = None
    modbus_tcp_enabled: bool | None = None
    api_enabled: bool | None = None
    manufacturer: str | None = None
    model: str | None = None
    install_year: int | None = None
    nominal_capacity_kg_year: float | None = None
    actual_capacity_kg_year: float | None = None
    min_line_speed_m_min: float | None = None
    max_line_speed_m_min: float | None = None
    layer_structure_type: str | None = None
    screw_diameter_mm: float | None = None
    ld_ratio: float | None = None
    suitable_polymer_codes: list[str] | None = None
    pcr_capable: bool | None = None
    pir_capable: bool | None = None
    max_pcr_technical_pct: float | None = None
    max_pir_technical_pct: float | None = None
    gravimetric_dosing_equipped: bool | None = None
    online_thickness_control: bool | None = None
    energy_metering_equipped: bool | None = None
    average_waste_rate_pct: float | None = None
    availability_status: str | None = None
