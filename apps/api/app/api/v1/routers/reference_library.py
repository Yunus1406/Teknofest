"""Faz F — Ambalaj Referans Veri Kütüphanesi: salt-okunur `GET /reference/*`
uçları. Mevcut `/kb/*` (app/api/v1/routers/knowledge.py) ve firma-özel
`/cost-factors`'a (app/api/v1/routers/cost.py) DOKUNMAZ -- bu router SADECE
Faz F'te eklenen yeni sistem-referans tablolarını sunar. F.13'ün Referans
Merkezi Ekranı bu uçları kategori kategori tüketir."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.chemical_restriction import ChemicalRestriction
from app.models.cost_reference import BenchmarkReference, CostReferenceFactor
from app.models.food_contact_requirement import FoodContactRequirement
from app.models.mechanical_test_standard import MechanicalTestStandard
from app.models.recyclability_criterion import RecyclabilityCriterion
from app.models.regulation_requirement import RegulationRequirement
from app.models.technical_reference import (
    LayerStructureReference,
    PolymerTechnicalReference,
    ProcessReference,
)
from app.schemas.reference_library import (
    BenchmarkReferenceOut,
    ChemicalRestrictionOut,
    CostReferenceFactorOut,
    FoodContactRequirementOut,
    LayerStructureReferenceOut,
    MechanicalTestStandardOut,
    PolymerTechnicalReferenceOut,
    ProcessReferenceOut,
    RecyclabilityCriterionOut,
    RegulationRequirementOut,
)

router = APIRouter(prefix="/reference", tags=["Referans Veri Kütüphanesi"])


@router.get("/regulation-requirements", response_model=list[RegulationRequirementOut])
def list_regulation_requirements(db: Session = Depends(get_db)):
    return db.query(RegulationRequirement).all()


@router.get("/chemical-restrictions", response_model=list[ChemicalRestrictionOut])
def list_chemical_restrictions(db: Session = Depends(get_db)):
    return db.query(ChemicalRestriction).all()


@router.get("/food-contact-requirements", response_model=list[FoodContactRequirementOut])
def list_food_contact_requirements(db: Session = Depends(get_db)):
    return db.query(FoodContactRequirement).all()


@router.get("/polymer-technical", response_model=list[PolymerTechnicalReferenceOut])
def list_polymer_technical_references(db: Session = Depends(get_db)):
    return db.query(PolymerTechnicalReference).all()


@router.get("/process-parameters", response_model=list[ProcessReferenceOut])
def list_process_references(db: Session = Depends(get_db)):
    return db.query(ProcessReference).all()


@router.get("/layer-structures", response_model=list[LayerStructureReferenceOut])
def list_layer_structure_references(db: Session = Depends(get_db)):
    return db.query(LayerStructureReference).all()


@router.get("/mechanical-test-standards", response_model=list[MechanicalTestStandardOut])
def list_mechanical_test_standards(db: Session = Depends(get_db)):
    return db.query(MechanicalTestStandard).all()


@router.get("/recyclability-criteria", response_model=list[RecyclabilityCriterionOut])
def list_recyclability_criteria(db: Session = Depends(get_db)):
    return db.query(RecyclabilityCriterion).all()


@router.get("/cost-benchmarks", response_model=list[CostReferenceFactorOut])
def list_cost_reference_factors(db: Session = Depends(get_db)):
    return db.query(CostReferenceFactor).all()


@router.get("/benchmarks", response_model=list[BenchmarkReferenceOut])
def list_benchmark_references(db: Session = Depends(get_db)):
    """Faz F.11 — bilinçli olarak boş kalabilir (bkz.
    knowledge_base/data/benchmark_reference.yaml); boş bir liste dönmesi
    HATA DEĞİLDİR."""
    return db.query(BenchmarkReference).all()
