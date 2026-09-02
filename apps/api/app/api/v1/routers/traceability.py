"""Faz B.9 — Firma Hafızası Zinciri: tek bir salt okunur izlenebilirlik
sorgusu. Yeni tablo yok; B.1-B.8'de kurulan FK'ler üzerinden JOIN yapılır
(bkz. app/services/traceability_service.py)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.learning_memory import LifecycleEventOut
from app.schemas.traceability import ConversionStoryOut, DigitalTwinOut, RecipeTraceabilityOut
from app.services.digital_twin_service import build_digital_twin
from app.services.lifecycle_service import build_lifecycle_timeline
from app.services.story_service import build_conversion_story
from app.services.traceability_service import build_recipe_traceability

router = APIRouter(prefix="/traceability", tags=["Firma Hafızası Zinciri"])


@router.get("/recipes/{recipe_id}", response_model=RecipeTraceabilityOut)
def get_recipe_traceability(recipe_id: str, db: Session = Depends(get_db)):
    result = build_recipe_traceability(db, recipe_id)
    if result is None:
        raise HTTPException(404, "Reçete bulunamadı")
    return result


# --- Faz O.1 (Madde 18): Ambalajın Dijital İkizi ----------------------------

@router.get("/recipes/{recipe_id}/digital-twin", response_model=DigitalTwinOut)
def get_digital_twin(recipe_id: str, db: Session = Depends(get_db)):
    result = build_digital_twin(db, recipe_id)
    if result is None:
        raise HTTPException(404, "Reçete bulunamadı")
    return result


# --- Faz R.1 (Madde 26): Ambalaj Yaşam Döngüsü Zaman Çizelgesi -------------

@router.get("/recipes/{recipe_id}/lifecycle-timeline", response_model=list[LifecycleEventOut])
def get_lifecycle_timeline(recipe_id: str, db: Session = Depends(get_db)):
    result = build_lifecycle_timeline(db, recipe_id)
    if result is None:
        raise HTTPException(404, "Reçete bulunamadı")
    return result


# --- Faz S.2 (Madde 30): Bir Ambalajın Dönüşüm Hikâyesi ---------------------

@router.get("/recipes/{recipe_id}/conversion-story", response_model=ConversionStoryOut)
def get_conversion_story(recipe_id: str, db: Session = Depends(get_db)):
    try:
        result = build_conversion_story(db, recipe_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if result is None:
        raise HTTPException(404, "Reçete bulunamadı")
    return result
