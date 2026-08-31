"""Maliyet Veri Tabanı (Firma Gerçek Veri Kütüphanesi) — salt okunur
görünürlük. Faz B.7: bu veri henüz `optimization/scorer.py`'ye entegre
DEĞİL, sadece saklanıp listeleniyor (bkz. app/models/cost.py)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.cost import CostFactor
from app.schemas.cost import CostFactorOut

router = APIRouter(prefix="/cost-factors", tags=["Maliyet Veri Tabanı"])


@router.get("", response_model=list[CostFactorOut])
def list_cost_factors(db: Session = Depends(get_db)):
    return db.query(CostFactor).all()
