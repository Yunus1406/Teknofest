"""Faz B.9 — Firma Hafızası Zinciri: salt okunur izlenebilirlik sorgusu.
Yeni bir tablo YOK; B.1-B.8'de kurulan FK'ler üzerinden Company -> Facility
-> Machine -> SKU -> Recipe -> Material -> ProductionOrder -> WasteRecord ->
PhysicalTest -> Regulation -> CarbonEF zincirini geriye doğru izleyip tek bir
yapılandırılmış sözlükte toplar (bkz. app/api/v1/routers/traceability.py)."""
from sqlalchemy.orm import Session

from app.models.company import Facility
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Regulation
from app.models.production import PhysicalTest, ProductionOrder, WasteRecord
from app.models.recipe import PackagingRequest, Recipe, RegulatoryAssessment


def build_recipe_traceability(db: Session, recipe_id: str) -> dict | None:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        return None

    packaging_request = db.get(PackagingRequest, recipe.packaging_request_id)
    sku = packaging_request.sku if packaging_request is not None else None

    line = db.get(ProductionLine, recipe.line_id) if recipe.line_id else None
    facility = db.get(Facility, line.facility_id) if line and line.facility_id else None
    company = facility.company if facility is not None else None

    layers = []
    for layer in recipe.layers:
        material = layer.material
        carbon_ef = material.carbon_ef if material is not None else None
        layers.append(
            {
                "layer_index": layer.layer_index,
                "layer_label": layer.layer_label,
                "ratio_pct": layer.ratio_pct,
                "thickness_micron": layer.thickness_micron,
                "material": (
                    {"id": material.id, "name": material.name, "material_type": material.material_type}
                    if material is not None
                    else None
                ),
                "carbon_ef": (
                    {
                        "id": carbon_ef.id,
                        "ef_value": carbon_ef.ef_value,
                        "unit": carbon_ef.unit,
                        "is_demo_placeholder": carbon_ef.is_demo_placeholder,
                        "source": carbon_ef.source,
                    }
                    if carbon_ef is not None
                    else None
                ),
            }
        )

    orders_out = []
    for order in db.query(ProductionOrder).filter_by(recipe_id=recipe.id).all():
        waste_records = db.query(WasteRecord).filter_by(production_order_id=order.id).all()
        orders_out.append(
            {
                "id": order.id,
                "status": order.status,
                "scheduled_qty_units": order.scheduled_qty_units,
                "operator": order.operator,
                "waste_records": [
                    {"waste_type": w.waste_type, "kg": w.kg, "recoverable": w.recoverable}
                    for w in waste_records
                ],
            }
        )

    physical_tests = db.query(PhysicalTest).filter_by(recipe_id=recipe.id).all()

    regulatory_assessments = []
    if packaging_request is not None:
        assessments = (
            db.query(RegulatoryAssessment).filter_by(packaging_request_id=packaging_request.id).all()
        )
        for a in assessments:
            reg = db.get(Regulation, a.regulation_id)
            regulatory_assessments.append(
                {
                    "regulation_code": reg.code if reg is not None else None,
                    "verdict": a.verdict,
                    "reasoning": a.reasoning,
                }
            )

    return {
        "recipe_id": recipe.id,
        "company": {"id": company.id, "name": company.name} if company is not None else None,
        "facility": (
            {"id": facility.id, "name": facility.name, "address": facility.address}
            if facility is not None
            else None
        ),
        "machine": (
            {"id": line.id, "name": line.name, "process_type": line.process_type}
            if line is not None
            else None
        ),
        "sku": {"id": sku.id, "sku_code": sku.sku_code, "product_name": sku.product_name} if sku is not None else None,
        "packaging_request": (
            {
                "id": packaging_request.id,
                "packaging_type": packaging_request.packaging_type,
                "product": packaging_request.product,
            }
            if packaging_request is not None
            else None
        ),
        "recipe": {
            "id": recipe.id,
            "version": recipe.version,
            "status": recipe.status,
            "is_verified": recipe.is_verified,
            "total_micron": recipe.total_micron,
            "total_gsm": recipe.total_gsm,
        },
        "layers": layers,
        "production_orders": orders_out,
        "physical_tests": [
            {"test_type": t.test_type, "value": t.value, "unit": t.unit, "passed": t.passed}
            for t in physical_tests
        ],
        "regulatory_assessments": regulatory_assessments,
    }
