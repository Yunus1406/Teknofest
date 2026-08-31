"""Faz B.9 — Firma Hafızası Zinciri: tek bir salt okunur izlenebilirlik
sorgusu. Yeni tablo yok; B.1-B.8'de kurulan FK'ler üzerinden JOIN yapılır
(bkz. app/services/traceability_service.py)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.traceability import RecipeTraceabilityOut
from app.services.traceability_service import build_recipe_traceability

router = APIRouter(prefix="/traceability", tags=["Firma Hafızası Zinciri"])


@router.get("/recipes/{recipe_id}", response_model=RecipeTraceabilityOut)
def get_recipe_traceability(recipe_id: str, db: Session = Depends(get_db)):
    result = build_recipe_traceability(db, recipe_id)
    if result is None:
        raise HTTPException(404, "Reçete bulunamadı")
    return result
