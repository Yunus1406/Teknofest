"""Faz E.2 — Makine Parkı: "Yeni Makine Ekle" ve mevcut hat güncelleme.
`app/api/v1/routers/knowledge.py`'deki GET /kb/production-lines (salt okunur
liste) DEĞİŞTİRİLMEDİ — bu router sadece yazma uçlarını ekler."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.infrastructure import ProductionLine
from app.schemas.infrastructure import ProductionLineCreate, ProductionLineOut, ProductionLineUpdate

router = APIRouter(prefix="/production-lines", tags=["Makine Parkı"])


@router.post("", response_model=ProductionLineOut)
def create_production_line(payload: ProductionLineCreate, db: Session = Depends(get_db)):
    line = ProductionLine(**payload.model_dump())
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@router.put("/{line_id}", response_model=ProductionLineOut)
def update_production_line(line_id: str, payload: ProductionLineUpdate, db: Session = Depends(get_db)):
    line = db.get(ProductionLine, line_id)
    if line is None:
        raise HTTPException(404, "Üretim hattı bulunamadı.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(line, field, value)
    db.commit()
    db.refresh(line)
    return line
