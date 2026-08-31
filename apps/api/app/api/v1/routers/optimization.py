"""Aşama 6-7 — Optimizasyon (ANA MOTOR) ve Reçete Önerileri.
Bu router, kısıt motoru + çok amaçlı optimizasyon + LLM gerekçelendirmeyi
tek bir uçtan uca koşuda çalıştırır ve sonucu kalıcı reçetelerle birlikte
döner."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.models.optimization import OptimizationCandidate, OptimizationRun
from app.models.recipe import Recipe
from app.schemas.optimization import EliminatedCandidateOut, OptimizationCandidateOut, OptimizationRunOut
from app.services import optimization_service

router = APIRouter(prefix="/optimization", tags=["Aşama 6-7 - Optimizasyon & Reçete Önerileri"])


def _load_candidate_with_recipe(db: Session, candidate_id: str) -> OptimizationCandidate:
    candidate = (
        db.query(OptimizationCandidate)
        .filter_by(id=candidate_id)
        .options(
            selectinload(OptimizationCandidate.recipe).selectinload(Recipe.layers),
            selectinload(OptimizationCandidate.recipe).selectinload(Recipe.additives),
            selectinload(OptimizationCandidate.recipe).selectinload(Recipe.evaluations),
            selectinload(OptimizationCandidate.recipe).selectinload(Recipe.metrics),
        )
        .one()
    )
    return candidate


@router.post("/requests/{request_id}/run", response_model=OptimizationRunOut)
def run_optimization(
    request_id: str, line_id: str, ratio_step_pct: int = 10, db: Session = Depends(get_db)
):
    try:
        result = optimization_service.run_optimization(db, request_id, line_id, ratio_step_pct)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    finalists = [
        _load_candidate_with_recipe(db, cid) for cid in result["finalist_candidate_ids"]
    ]
    return OptimizationRunOut(
        id=result["run"].id,
        packaging_request_id=request_id,
        finalists=[OptimizationCandidateOut.model_validate(f) for f in finalists],
        notable_eliminated=[EliminatedCandidateOut(**e) for e in result["notable_eliminated"]],
        generated_candidate_count=result["generated_candidate_count"],
        survived_constraint_engine_count=result["survived_constraint_engine_count"],
    )


@router.get("/runs/{run_id}", response_model=OptimizationRunOut)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(OptimizationRun, run_id)
    if run is None:
        raise HTTPException(404, "Optimizasyon koşusu bulunamadı")
    finalists = [
        _load_candidate_with_recipe(db, c.id) for c in run.candidates if c.is_finalist
    ]
    return OptimizationRunOut(
        id=run.id,
        packaging_request_id=run.packaging_request_id,
        finalists=[OptimizationCandidateOut.model_validate(f) for f in finalists],
        notable_eliminated=[],
        generated_candidate_count=run.parameters.get("candidate_count_generated", 0),
        survived_constraint_engine_count=run.parameters.get("survived_constraint_engine_count", 0),
    )
