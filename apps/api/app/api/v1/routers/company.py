"""Faz E.1 — Firma Profili. Tek kiracılı MVP: sistemde en fazla bir
`Company` satırı olur (bkz. app/models/company.py). Bir Company yoksa
GET 404 döner — sessizce boş/uydurma bir satır OLUŞTURULMAZ; frontend
önce POST ile firmayı gerçekten kurar."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.company import Company, Facility
from app.schemas.company import (
    CompanyBenchmarkCreate,
    CompanyBenchmarkOut,
    CompanyCreate,
    CompanyOut,
    CompanyProfileOut,
    CompanyUpdate,
    FacilityOut,
    FacilityUpsert,
)
from app.services import company_benchmark_service

router = APIRouter(prefix="/company", tags=["Firma Profili"])


def _get_singleton_company(db: Session) -> Company | None:
    return db.query(Company).first()


def _get_singleton_company_or_404(db: Session) -> Company:
    company = _get_singleton_company(db)
    if company is None:
        raise HTTPException(404, "Firma profili henüz oluşturulmadı.")
    return company


@router.get("/profile", response_model=CompanyProfileOut)
def get_profile(db: Session = Depends(get_db)):
    company = _get_singleton_company_or_404(db)
    return CompanyProfileOut(company=company, facilities=company.facilities)


@router.post("/profile", response_model=CompanyProfileOut)
def create_profile(payload: CompanyCreate, db: Session = Depends(get_db)):
    if _get_singleton_company(db) is not None:
        raise HTTPException(400, "Firma profili zaten var; güncellemek için PUT kullanın.")
    company = Company(**payload.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return CompanyProfileOut(company=company, facilities=[])


@router.put("/profile", response_model=CompanyProfileOut)
def update_profile(payload: CompanyUpdate, db: Session = Depends(get_db)):
    company = _get_singleton_company_or_404(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return CompanyProfileOut(company=company, facilities=company.facilities)


@router.post("/facilities", response_model=FacilityOut)
def create_facility(payload: FacilityUpsert, db: Session = Depends(get_db)):
    company = _get_singleton_company_or_404(db)
    facility = Facility(company_id=company.id, **payload.model_dump())
    db.add(facility)
    db.commit()
    db.refresh(facility)
    return facility


@router.put("/facilities/{facility_id}", response_model=FacilityOut)
def update_facility(facility_id: str, payload: FacilityUpsert, db: Session = Depends(get_db)):
    facility = db.get(Facility, facility_id)
    if facility is None:
        raise HTTPException(404, "Tesis bulunamadı.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(facility, field, value)
    db.commit()
    db.refresh(facility)
    return facility


# --- Faz N.2 (Madde 15): Benchmark Verileri -------------------------------

@router.get("/benchmarks", response_model=list[CompanyBenchmarkOut])
def list_company_benchmarks(db: Session = Depends(get_db)):
    company = _get_singleton_company_or_404(db)
    return company_benchmark_service.list_benchmarks(db, company.id)


@router.post("/benchmarks", response_model=CompanyBenchmarkOut)
def create_company_benchmark(payload: CompanyBenchmarkCreate, db: Session = Depends(get_db)):
    company = _get_singleton_company_or_404(db)
    try:
        return company_benchmark_service.create_benchmark(db, company.id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/benchmarks/{benchmark_id}", status_code=204)
def delete_company_benchmark(benchmark_id: str, db: Session = Depends(get_db)):
    company = _get_singleton_company_or_404(db)
    deleted = company_benchmark_service.delete_benchmark(db, company.id, benchmark_id)
    if not deleted:
        raise HTTPException(404, "Benchmark kaydı bulunamadı.")
