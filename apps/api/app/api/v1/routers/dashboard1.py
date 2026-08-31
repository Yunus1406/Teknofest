"""Aşama 1 — Ana Ekran: firmanın genel sürdürülebilirlik durumu."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.enums import RegulatoryVerdict
from app.models.recipe import Recipe, RegulatoryAssessment
from app.schemas.dashboard import DashboardSummaryOut
from app.services import dashboard_aggregation

router = APIRouter(prefix="/dashboard1", tags=["Aşama 1 - Ana Ekran"])


@router.get("/summary", response_model=DashboardSummaryOut)
def get_summary(db: Session = Depends(get_db)) -> DashboardSummaryOut:
    case_counts = dashboard_aggregation.count_cases_by_status(db)
    active_cases = sum(
        count
        for status, count in case_counts.items()
        if status != dashboard_aggregation.TAMAMLANDI
    )
    completed_cases = case_counts[dashboard_aggregation.TAMAMLANDI]

    verified_recipes = db.query(Recipe).filter(Recipe.is_verified.is_(True)).count()

    totals = dashboard_aggregation.compute_material_usage_totals(db)
    realized = dashboard_aggregation.compute_realized_and_gains(db)

    regulatory_alerts = (
        db.query(RegulatoryAssessment)
        .filter(RegulatoryAssessment.verdict != RegulatoryVerdict.OK.value)
        .count()
    )

    return DashboardSummaryOut(
        active_cases=active_cases,
        completed_cases=completed_cases,
        verified_recipes=verified_recipes,
        total_virgin_kg=totals.virgin_kg,
        total_pcr_kg=totals.pcr_kg,
        total_regranule_kg=totals.regranul_kg,
        total_virgin_pct=totals.pct(totals.virgin_kg),
        total_pcr_pct=totals.pct(totals.pcr_kg),
        total_regranule_pct=totals.pct(totals.regranul_kg),
        realized_waste_kg=realized.realized_waste_kg,
        prevented_waste_kg=realized.prevented_waste_kg,
        carbon_reduction_kg_co2=realized.carbon_reduction_kg_co2,
        carbon_data_quality=realized.carbon_data_quality,
        regulatory_alerts=regulatory_alerts,
    )
