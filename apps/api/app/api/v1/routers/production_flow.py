"""Aşama 8-12: Karşılaştırma, Üretime Aktarım, Canlı Takip (simüle),
Fiziksel Doğrulama, Nihai Sonuç."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.digital_product_passport import DigitalProductPassport
from app.models.mechanical_test_standard import MechanicalTestStandard
from app.models.production import PhysicalTest, ProductionOrder, WasteRecord
from app.models.recipe import Recipe
from app.schemas.dashboard import ComparisonOut, FinalResultOut
from app.schemas.production import (
    PhysicalTestOut,
    PhysicalVerificationSubmit,
    ProductionLiveDataOut,
    ProductionOrderOut,
    SuggestedTestTargetOut,
    WasteRecordOut,
)
from app.schemas.recipe import RecipeOut
from app.services import passport_service, pdf_service, production_flow_service, report_service
from app.services.test_targets import suggested_physical_test_targets

router = APIRouter(prefix="/production-flow", tags=["Aşama 8-12 - Üretim & Doğrulama & Sonuç"])


def _get_recipe_or_404(db: Session, recipe_id: str) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(404, "Reçete bulunamadı")
    return recipe


def _get_order_or_404(db: Session, order_id: str) -> ProductionOrder:
    order = db.get(ProductionOrder, order_id)
    if order is None:
        raise HTTPException(404, "Üretim emri bulunamadı")
    return order


@router.get("/recipes/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: str, db: Session = Depends(get_db)):
    return _get_recipe_or_404(db, recipe_id)


# --- Aşama 8 -----------------------------------------------------------------

@router.get("/recipes/{recipe_id}/comparison", response_model=ComparisonOut)
def get_comparison(recipe_id: str, db: Session = Depends(get_db)):
    recipe = _get_recipe_or_404(db, recipe_id)
    return production_flow_service.build_comparison(db, recipe)


# --- Aşama 9 -----------------------------------------------------------------

@router.post("/recipes/{recipe_id}/production-orders", response_model=ProductionOrderOut)
def create_production_order(recipe_id: str, qty_units: int, db: Session = Depends(get_db)):
    recipe = _get_recipe_or_404(db, recipe_id)
    if not recipe.line_id:
        raise HTTPException(400, "Reçeteye atanmış bir üretim hattı yok")
    return production_flow_service.create_production_order(db, recipe, qty_units)


# --- Aşama 10 (simüle) --------------------------------------------------------

@router.post("/production-orders/{order_id}/simulate-live-data", response_model=list[ProductionLiveDataOut])
def simulate_live_data(order_id: str, db: Session = Depends(get_db)):
    order = _get_order_or_404(db, order_id)
    rows = production_flow_service.simulate_live_data(db, order)
    return [
        ProductionLiveDataOut(
            ts=r.ts.isoformat() if r.ts else None,
            produced_qty_units=r.produced_qty_units,
            period_produced_qty_units=r.period_produced_qty_units,
            material_consumption=r.material_consumption,
            line_speed_m_min=r.line_speed_m_min,
            energy_kwh=r.energy_kwh,
            cumulative_energy_kwh=r.cumulative_energy_kwh,
            waste_kg=r.waste_kg,
            cumulative_waste_kg=r.cumulative_waste_kg,
            source=r.source,
        )
        for r in rows
    ]


@router.get("/production-orders/{order_id}/waste-records", response_model=list[WasteRecordOut])
def list_waste_records(order_id: str, db: Session = Depends(get_db)):
    """Faz B.6 — `ProductionLiveData.waste_kg` dönemsel toplamının tipli
    kırılımı (start-up, kenar firesi, bobin değişimi, kalite reddi vb.)."""
    _get_order_or_404(db, order_id)
    return (
        db.query(WasteRecord)
        .filter(WasteRecord.production_order_id == order_id)
        .order_by(WasteRecord.ts)
        .all()
    )


# --- Aşama 11 -----------------------------------------------------------------

@router.get("/recipes/{recipe_id}/suggested-test-targets", response_model=list[SuggestedTestTargetOut])
def get_suggested_test_targets(recipe_id: str, db: Session = Depends(get_db)):
    recipe = _get_recipe_or_404(db, recipe_id)
    # Faz F.6 — kategoriye özgü satır varsa onu, yoksa genel (None) satırı
    # kullan; DB sorgusu burada yapılır çünkü suggested_physical_test_targets
    # kasıtlı olarak saf/DB'siz kalır (bkz. test_targets.py docstring'i).
    mechanical_references: dict[str, MechanicalTestStandard] = {}
    for row in db.query(MechanicalTestStandard).filter(MechanicalTestStandard.packaging_category.is_(None)).all():
        mechanical_references[row.test_type] = row
    return suggested_physical_test_targets(recipe, mechanical_references)


class PhysicalVerificationResultOut(BaseModel):
    all_passed: bool
    results: list[PhysicalTestOut] = []
    new_recipe_version: RecipeOut | None = None


@router.post("/physical-verification", response_model=PhysicalVerificationResultOut)
def submit_physical_verification(payload: PhysicalVerificationSubmit, db: Session = Depends(get_db)):
    order = _get_order_or_404(db, payload.production_order_id)
    try:
        rows, new_version = production_flow_service.submit_physical_tests(
            db, order, [t.model_dump() for t in payload.tests]
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return PhysicalVerificationResultOut(
        all_passed=all(r.passed for r in rows),
        results=[PhysicalTestOut.model_validate(r) for r in rows],
        new_recipe_version=new_version,
    )


# --- Aşama 12 -----------------------------------------------------------------

@router.post("/recipes/{recipe_id}/finalize", response_model=FinalResultOut)
def finalize_result(recipe_id: str, db: Session = Depends(get_db)):
    recipe = _get_recipe_or_404(db, recipe_id)
    try:
        result = production_flow_service.finalize_result(db, recipe)
    except ValueError as e:
        raise HTTPException(400, str(e))
    tests = db.query(PhysicalTest).filter_by(recipe_id=recipe.id).all()
    tests_passed = all(t.passed for t in tests) if tests else False
    return FinalResultOut(
        recipe_id=recipe.id,
        per_1000_units=result.per_1000_units,
        physical_tests_passed=tests_passed,
        version_history=production_flow_service.version_history(db, recipe),
    )


# --- Faz C.5-C.7: Otomatik Optimizasyon Raporu (PDF) ---------------------

@router.get("/recipes/{recipe_id}/optimization-report")
def get_optimization_report(
    recipe_id: str, format: Literal["technical", "executive"] = "technical", db: Session = Depends(get_db)
):
    """Dashboard 12'nin doğal uzantısı — Stage 2-12 arasında biriken TÜM
    doğrulanmış veriden otomatik derlenen PDF (bkz. app/services/
    report_service.py + pdf_service.py). Sadece `recipe.is_verified=True`
    reçeteler için üretilebilir (DPP ile aynı ön koşul)."""
    recipe = _get_recipe_or_404(db, recipe_id)
    try:
        data = report_service.build_optimization_report_data(db, recipe.id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    passport_row = db.query(DigitalProductPassport).filter_by(recipe_id=recipe.id).one_or_none()
    passport_info = None
    if passport_row is not None:
        # QR SADECE gerçek bir pasaport varsa eklenir -- passport_service
        # zaten kurulu QR üretim mantığı burada TEKRAR KURULMUYOR, çağrılıyor.
        content = passport_service.build_passport_content(db, passport_row, include_authorized=False)
        passport_info = {"passport_no": passport_row.passport_no, "qr_code_data_uri": content["qr_code_data_uri"]}

    if format == "executive":
        pdf_bytes = pdf_service.render_executive_summary(data, passport=passport_info)
        filename = f"yonetici-ozeti-{recipe.id[:8]}.pdf"
    else:
        pdf_bytes = pdf_service.render_technical_report(data, passport=passport_info)
        filename = f"optimizasyon-raporu-{recipe.id[:8]}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
