"""Faz E.3 — Hammadde ve Malzeme Kütüphanesi: "Yeni Hammadde/Katkı Ekle" ve
güncelleme uçları. `app/api/v1/routers/knowledge.py`'deki GET /kb/materials
(salt okunur liste) DEĞİŞTİRİLMEDİ — bu router sadece yazma uçlarını ekler.

`_MATERIAL_CLASS_BY_TYPE` deseni app/knowledge_base/loader.py ile AYNIDIR:
material_type'a göre Material/PcrMaterial/PirMaterial'dan doğru polymorphic
alt sınıf örneklenir — PCR ve PIR ASLA aynı Python sınıfına yazılmaz (bkz.
app/models/knowledge.py modül docstring'i, Faz B.2)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.knowledge import Additive, Material, PcrMaterial, PirMaterial, Polymer
from app.schemas.knowledge import (
    AdditiveCreate,
    AdditiveOut,
    AdditiveUpdate,
    MaterialCreate,
    MaterialOut,
    MaterialUpdate,
    SupplierEvidenceRadarOut,
)
from app.services.supplier_risk_service import build_supplier_evidence_radar

router = APIRouter(tags=["Hammadde Kütüphanesi"])

_MATERIAL_CLASS_BY_TYPE: dict[str, type[Material]] = {
    "virgin": Material,
    "pcr": PcrMaterial,
    "regranul": PirMaterial,
}

# Yalnızca ilgili polymorphic alt sınıfın gerçekten taşıdığı alanlar — diğer
# tiplerde payload'da gelse bile sessizce yok sayılır (loader.py'deki
# type_fields deseniyle aynı).
_PCR_ONLY_FIELDS = {"contamination_level", "odor_level", "technical_constraints", "post_consumer_content_pct"}
_PIR_ONLY_FIELDS = {"source_process", "production_date", "source_machine_id", "source_recipe_id"}


@router.post("/materials", response_model=MaterialOut)
def create_material(payload: MaterialCreate, db: Session = Depends(get_db)):
    model_cls = _MATERIAL_CLASS_BY_TYPE.get(payload.material_type)
    if model_cls is None:
        raise HTTPException(400, f"Geçersiz material_type: '{payload.material_type}'. Beklenen: virgin/pcr/regranul.")
    if db.get(Polymer, payload.polymer_id) is None:
        raise HTTPException(400, "Belirtilen polymer_id bulunamadı.")

    data = payload.model_dump()
    if payload.material_type != "pcr":
        for f in _PCR_ONLY_FIELDS:
            data.pop(f, None)
    if payload.material_type != "regranul":
        for f in _PIR_ONLY_FIELDS:
            data.pop(f, None)

    material = model_cls(**data)
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@router.put("/materials/{material_id}", response_model=MaterialOut)
def update_material(material_id: str, payload: MaterialUpdate, db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(404, "Hammadde bulunamadı.")

    updates = payload.model_dump(exclude_unset=True)
    if material.material_type != "pcr":
        for f in _PCR_ONLY_FIELDS:
            updates.pop(f, None)
    if material.material_type != "regranul":
        for f in _PIR_ONLY_FIELDS:
            updates.pop(f, None)

    for field, value in updates.items():
        setattr(material, field, value)
    db.commit()
    db.refresh(material)
    return material


# --- Faz R.3 (Madde 28): Tedarikçi ve Hammadde Risk Radarı -----------------

@router.get("/materials/{material_id}/supplier-evidence-radar", response_model=SupplierEvidenceRadarOut)
def get_supplier_evidence_radar(material_id: str, db: Session = Depends(get_db)):
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(404, "Hammadde bulunamadı.")
    return build_supplier_evidence_radar(material)


@router.post("/additives", response_model=AdditiveOut)
def create_additive(payload: AdditiveCreate, db: Session = Depends(get_db)):
    additive = Additive(**payload.model_dump())
    db.add(additive)
    db.commit()
    db.refresh(additive)
    return additive


@router.put("/additives/{additive_id}", response_model=AdditiveOut)
def update_additive(additive_id: str, payload: AdditiveUpdate, db: Session = Depends(get_db)):
    additive = db.get(Additive, additive_id)
    if additive is None:
        raise HTTPException(404, "Katkı maddesi bulunamadı.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(additive, field, value)
    db.commit()
    db.refresh(additive)
    return additive
