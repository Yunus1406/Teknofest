from pydantic import BaseModel, ConfigDict


class ProductSkuCreate(BaseModel):
    sku_code: str
    product_name: str
    packaging_type: str
    usage_area: str
    customer: str | None = None
    target_market: str
    food_contact: bool = False
    dimensions: dict = {}
    film_thickness_micron: float | None = None
    gsm: float | None = None
    layer_count: int | None = None
    layer_structure: str | None = None
    line_id: str | None = None
    technical_spec_ref: str | None = None
    physical_test_criteria: dict = {}


class ProductSkuOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sku_code: str
    product_name: str
    packaging_type: str
    usage_area: str
    customer: str | None = None
    target_market: str
    food_contact: bool
    dimensions: dict
    film_thickness_micron: float | None = None
    gsm: float | None = None
    layer_count: int | None = None
    layer_structure: str | None = None
    line_id: str | None = None
    current_recipe_id: str | None = None
    technical_spec_ref: str | None = None
    physical_test_criteria: dict
