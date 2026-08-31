from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CostFactorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    facility_id: str
    currency: str
    electricity_rate: float | None = None
    gas_rate: float | None = None
    labor_rate: float | None = None
    waste_disposal_cost: float | None = None
    recovery_cost: float | None = None
    machine_hour_rate: float | None = None
    effective_date: datetime
    is_demo_placeholder: bool
    source: str | None = None
