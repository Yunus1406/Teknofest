"""Faz E.1 — Firma Profili. `bool | None` alanlar `None` = "Veri Girilmedi"
anlamına gelir (bkz. app/models/company.py modül docstring'i)."""
from pydantic import BaseModel, ConfigDict


class FacilityUpsert(BaseModel):
    name: str
    address: str | None = None
    code: str | None = None
    production_area_m2: float | None = None
    annual_capacity_tons: float | None = None
    working_days_per_year: int | None = None
    shift_count: int | None = None
    working_hours_per_day: float | None = None
    main_processes: list[str] = []
    electricity_consumption_kwh_year: float | None = None
    gas_consumption_m3_year: float | None = None
    renewable_energy_used: bool | None = None
    renewable_energy_pct: float | None = None


class FacilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    company_id: str
    name: str
    address: str | None = None
    code: str | None = None
    production_area_m2: float | None = None
    annual_capacity_tons: float | None = None
    working_days_per_year: int | None = None
    shift_count: int | None = None
    working_hours_per_day: float | None = None
    main_processes: list[str] = []
    electricity_consumption_kwh_year: float | None = None
    gas_consumption_m3_year: float | None = None
    renewable_energy_used: bool | None = None
    renewable_energy_pct: float | None = None


class CompanyCreate(BaseModel):
    name: str
    trade_name: str | None = None
    tax_country: str | None = None
    country: str | None = None
    city: str | None = None
    website: str | None = None
    business_area: str | None = None
    nace_code: str | None = None
    employee_count: int | None = None
    annual_production_capacity_tons: float | None = None
    annual_actual_production_tons: float | None = None
    main_export_markets: list[str] = []
    exports_to_eu: bool | None = None
    produces_food_packaging: bool | None = None
    logo_url: str | None = None


class CompanyUpdate(BaseModel):
    name: str | None = None
    trade_name: str | None = None
    tax_country: str | None = None
    country: str | None = None
    city: str | None = None
    website: str | None = None
    business_area: str | None = None
    nace_code: str | None = None
    employee_count: int | None = None
    annual_production_capacity_tons: float | None = None
    annual_actual_production_tons: float | None = None
    main_export_markets: list[str] | None = None
    exports_to_eu: bool | None = None
    produces_food_packaging: bool | None = None
    logo_url: str | None = None


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    trade_name: str | None = None
    tax_country: str | None = None
    country: str | None = None
    city: str | None = None
    website: str | None = None
    business_area: str | None = None
    nace_code: str | None = None
    employee_count: int | None = None
    annual_production_capacity_tons: float | None = None
    annual_actual_production_tons: float | None = None
    main_export_markets: list[str] = []
    exports_to_eu: bool | None = None
    produces_food_packaging: bool | None = None
    logo_url: str | None = None


class CompanyProfileOut(BaseModel):
    company: CompanyOut
    facilities: list[FacilityOut]
