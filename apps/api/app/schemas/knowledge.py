from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PolymerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    category: str
    base_properties: dict


class MaterialOut(BaseModel):
    """Hammadde Teknik Kartı. `material_type`'a göre yalnızca ilgili alanlar
    dolu olur: 'pcr' -> contamination_level/odor_level/technical_constraints;
    'regranul' (=PIR) -> source_process/production_date/source_machine_id/
    source_recipe_id. Tek şema kullanılıyor (polymorphic alt tip şeması
    yerine) çünkü frontend'de tek bir liste/tablo olarak gösteriliyor."""

    model_config = ConfigDict(from_attributes=True)
    id: str
    polymer_id: str
    name: str
    material_type: str
    source: str | None = None

    # Genel teknik kart (virgin/PCR/PIR ortak)
    manufacturer: str | None = None
    supplier: str | None = None
    color: str | None = None
    certification_status: str | None = None
    suitable_layer_position: str | None = None
    mfi_g_10min: float | None = None
    density_g_cm3: float | None = None
    degradation_factor: float
    tensile_strength_mpa: float | None = None
    elongation_pct: float | None = None
    dart_impact_g: float | None = None
    melt_temp_c: float | None = None
    processing_temp_c: float | None = None
    additive_content_note: str | None = None
    food_contact_eligible: bool
    max_recommended_ratio_pct: float
    cost_per_kg: float
    carbon_factor_kg_co2_per_kg: float
    carbon_ef_id: str | None = None
    stock_qty_kg: float | None = None
    lot_number: str | None = None

    # Faz E.3 — genişletilmiş teknik kart (virgin/PCR/PIR ortak)
    currency: str
    origin_country: str | None = None
    technical_datasheet_ref: str | None = None
    compliance_documents_ref: str | None = None

    # PCR'a özgü
    contamination_level: str | None = None
    odor_level: str | None = None
    technical_constraints: str | None = None
    post_consumer_content_pct: float | None = None

    # PIR/Regranül'e özgü (izlenebilirlik)
    source_process: str | None = None
    production_date: datetime | None = None
    source_machine_id: str | None = None
    source_recipe_id: str | None = None


class MaterialCreate(BaseModel):
    """`material_type` ayrımcı alanıdır: virgin/pcr/regranul — router bu
    değere göre Material/PcrMaterial/PirMaterial'dan doğru sınıfı oluşturur
    (bkz. app/knowledge_base/loader.py `_MATERIAL_CLASS_BY_TYPE`). Alt tipe
    özgü alanlar (ör. post_consumer_content_pct) yalnızca ilgili
    material_type için anlamlıdır; diğerlerinde sessizce yok sayılır."""

    polymer_id: str
    name: str
    material_type: str
    source: str | None = None

    manufacturer: str | None = None
    supplier: str | None = None
    color: str | None = None
    certification_status: str | None = None
    suitable_layer_position: str | None = None
    mfi_g_10min: float | None = None
    density_g_cm3: float | None = None
    degradation_factor: float = 0.0
    tensile_strength_mpa: float | None = None
    elongation_pct: float | None = None
    dart_impact_g: float | None = None
    melt_temp_c: float | None = None
    processing_temp_c: float | None = None
    additive_content_note: str | None = None
    food_contact_eligible: bool = True
    max_recommended_ratio_pct: float = 100.0
    cost_per_kg: float = 0.0
    carbon_factor_kg_co2_per_kg: float = 0.0
    carbon_ef_id: str | None = None
    stock_qty_kg: float | None = None
    lot_number: str | None = None

    currency: str = "TRY"
    origin_country: str | None = None
    technical_datasheet_ref: str | None = None
    compliance_documents_ref: str | None = None

    # PCR'a özgü
    contamination_level: str | None = None
    odor_level: str | None = None
    technical_constraints: str | None = None
    post_consumer_content_pct: float | None = None

    # PIR/Regranül'e özgü
    source_process: str | None = None
    production_date: datetime | None = None
    source_machine_id: str | None = None
    source_recipe_id: str | None = None


class MaterialUpdate(BaseModel):
    """`material_type` kasıtlı olarak dahil DEĞİL — bir kaydın polymorphic
    sınıfı (virgin/PCR/PIR) oluşturulduktan sonra değiştirilemez."""

    name: str | None = None
    source: str | None = None
    manufacturer: str | None = None
    supplier: str | None = None
    color: str | None = None
    certification_status: str | None = None
    suitable_layer_position: str | None = None
    mfi_g_10min: float | None = None
    density_g_cm3: float | None = None
    degradation_factor: float | None = None
    tensile_strength_mpa: float | None = None
    elongation_pct: float | None = None
    dart_impact_g: float | None = None
    melt_temp_c: float | None = None
    processing_temp_c: float | None = None
    additive_content_note: str | None = None
    food_contact_eligible: bool | None = None
    max_recommended_ratio_pct: float | None = None
    cost_per_kg: float | None = None
    carbon_factor_kg_co2_per_kg: float | None = None
    carbon_ef_id: str | None = None
    stock_qty_kg: float | None = None
    lot_number: str | None = None
    currency: str | None = None
    origin_country: str | None = None
    technical_datasheet_ref: str | None = None
    compliance_documents_ref: str | None = None
    contamination_level: str | None = None
    odor_level: str | None = None
    technical_constraints: str | None = None
    post_consumer_content_pct: float | None = None
    source_process: str | None = None
    production_date: datetime | None = None
    source_machine_id: str | None = None
    source_recipe_id: str | None = None


class CarbonEmissionFactorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    material_key: str
    factor_type: str
    ef_value: float
    unit: str
    source: str
    year: int | None = None
    geography: str | None = None
    version: str | None = None
    is_demo_placeholder: bool


class AdditiveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    additive_type: str
    manufacturer: str | None = None
    carrier_polymer: str | None = None
    regulatory_document_ref: str | None = None
    effects: dict
    dosage_min_pct: float
    dosage_max_pct: float
    food_contact_eligible: bool
    cost_per_kg: float
    carbon_ef_id: str | None = None


class AdditiveCreate(BaseModel):
    name: str
    additive_type: str
    manufacturer: str | None = None
    carrier_polymer: str | None = None
    regulatory_document_ref: str | None = None
    effects: dict = {}
    dosage_min_pct: float = 0.0
    dosage_max_pct: float = 2.0
    food_contact_eligible: bool = True
    cost_per_kg: float = 0.0
    carbon_ef_id: str | None = None


class AdditiveUpdate(BaseModel):
    name: str | None = None
    additive_type: str | None = None
    manufacturer: str | None = None
    carrier_polymer: str | None = None
    regulatory_document_ref: str | None = None
    effects: dict | None = None
    dosage_min_pct: float | None = None
    dosage_max_pct: float | None = None
    food_contact_eligible: bool | None = None
    cost_per_kg: float | None = None
    carbon_ef_id: str | None = None


class RegulationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    title: str
    category: str
    description: str
    criteria: dict
    applicable_packaging_types: list[str]


class SupplierEvidenceSignalOut(BaseModel):
    mevcut: bool
    aciklama: str


# Faz R.3 (Madde 28) — Tedarikçi ve Hammadde Risk Radarı (bkz.
# app/services/supplier_risk_service.py). CoA/SDS AYRI izlenmiyor --
# `uygunluk_belgeleri` sinyali bunları dürüstçe birleşik gösterir.
class SupplierEvidenceRadarOut(BaseModel):
    material_id: str
    material_name: str
    signals: dict[str, SupplierEvidenceSignalOut]
    tamlik_pct: float


class RegulationChangeImpactOut(BaseModel):
    """Faz L.4 (Madde 17) — bkz. app/services/regulation_impact_service.py."""

    regulation_code: str
    current_version: str | None
    total_active_skus: int
    affected_sku_count: int
    evidence_needed_count: int
    recipe_reassessment_count: int
    affected_sku_codes: list[str]
