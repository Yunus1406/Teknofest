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

    # PCR'a özgü
    contamination_level: str | None = None
    odor_level: str | None = None
    technical_constraints: str | None = None

    # PIR/Regranül'e özgü (izlenebilirlik)
    source_process: str | None = None
    production_date: datetime | None = None
    source_machine_id: str | None = None
    source_recipe_id: str | None = None


class CarbonEmissionFactorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    material_key: str
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


class RegulationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    title: str
    category: str
    description: str
    criteria: dict
    applicable_packaging_types: list[str]
