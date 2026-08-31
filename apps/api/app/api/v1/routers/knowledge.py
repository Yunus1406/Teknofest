"""Bilgi Tabanı okuma uçları — frontend'in malzeme/hat seçimi, mevzuat
görüntüleme gibi ihtiyaçları için."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Additive, CarbonEmissionFactor, Material, Polymer, Regulation
from app.schemas.infrastructure import ProductionLineOut
from app.schemas.knowledge import (
    AdditiveOut,
    CarbonEmissionFactorOut,
    MaterialOut,
    PolymerOut,
    RegulationOut,
)

router = APIRouter(prefix="/kb", tags=["Bilgi Tabanı"])


@router.get("/polymers", response_model=list[PolymerOut])
def list_polymers(db: Session = Depends(get_db)):
    return db.query(Polymer).all()


@router.get("/materials", response_model=list[MaterialOut])
def list_materials(db: Session = Depends(get_db)):
    return db.query(Material).all()


@router.get("/additives", response_model=list[AdditiveOut])
def list_additives(db: Session = Depends(get_db)):
    return db.query(Additive).all()


@router.get("/regulations", response_model=list[RegulationOut])
def list_regulations(db: Session = Depends(get_db)):
    return db.query(Regulation).all()


@router.get("/production-lines", response_model=list[ProductionLineOut])
def list_production_lines(db: Session = Depends(get_db)):
    return db.query(ProductionLine).all()


@router.get("/carbon-emission-factors", response_model=list[CarbonEmissionFactorOut])
def list_carbon_emission_factors(db: Session = Depends(get_db)):
    """Karbon Veri Kütüphanesi — bu fazda TÜM kayıtlar is_demo_placeholder=True
    (gerçek bir LCA veritabanı entegrasyonu yok, bkz. app/services/carbon.py)."""
    return db.query(CarbonEmissionFactor).all()
