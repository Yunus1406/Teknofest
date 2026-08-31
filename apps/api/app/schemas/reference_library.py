"""Faz F — Ambalaj Referans Veri Kütüphanesi yanıt şemaları. Tüm alt
kütüphaneler (F.1-F.11) buraya eklenir; salt-okunur GET uçları
`app/api/v1/routers/reference_library.py`'de tanımlıdır."""
from pydantic import BaseModel, ConfigDict


class RegulationRequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    regulation_id: str
    regulation_no: str
    article: str
    packaging_category: str | None = None
    target_year: int | None = None
    requirement_text: str
    pcr_only: bool
    exception_text: str | None = None
    version: str
    source: str | None = None
    default_verdict: str
    # Faz F.2
    threshold_value: float | None = None
    threshold_unit: str | None = None


class ChemicalRestrictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    substance_group: str
    restriction_type: str
    limit_value: float
    limit_unit: str
    food_contact_only: bool
    regulation_id: str | None = None
    source: str | None = None
    year: int | None = None
    version: str
    is_demo_placeholder: bool


class FoodContactRequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    regulation_id: str
    requirement_type: str
    substance: str | None = None
    limit_value: float | None = None
    limit_unit: str | None = None
    applies_to_pcr: bool
    notes: str | None = None
    source: str | None = None
    year: int | None = None
    version: str
    is_demo_placeholder: bool


class PolymerTechnicalReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    polymer_id: str
    property_name: str
    typical_min: float | None = None
    typical_max: float | None = None
    unit: str
    source: str | None = None
    year: int | None = None
    version: str
    is_demo_placeholder: bool


class ProcessReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    process_type: str
    parameter_name: str
    typical_min: float | None = None
    typical_max: float | None = None
    unit: str
    source: str | None = None
    year: int | None = None
    version: str
    is_demo_placeholder: bool


class LayerStructureReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    structure_pattern: str
    typical_usage: str
    barrier_properties: str
    source: str | None = None
    year: int | None = None
    version: str
    is_demo_placeholder: bool


class CostReferenceFactorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    cost_type: str
    typical_min: float | None = None
    typical_max: float | None = None
    unit: str
    currency: str
    source: str | None = None
    year: int | None = None
    geography: str | None = None
    version: str
    is_demo_placeholder: bool


class BenchmarkReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    packaging_category: str | None = None
    metric_name: str
    typical_value: float | None = None
    unit: str
    source: str | None = None
    year: int | None = None
    version: str
    is_demo_placeholder: bool


class RecyclabilityCriterionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    packaging_category: str | None = None
    dimension: str
    criterion_text: str
    weight_pct: float | None = None
    source: str | None = None
    year: int | None = None
    version: str
    is_demo_placeholder: bool


class MechanicalTestStandardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    test_type: str
    standard_name: str
    unit: str
    packaging_category: str | None = None
    typical_min: float | None = None
    typical_max: float | None = None
    source: str | None = None
    year: int | None = None
    version: str
    is_demo_placeholder: bool
