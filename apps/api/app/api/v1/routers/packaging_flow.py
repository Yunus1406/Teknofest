"""Aşama 2-5: Ambalaj Tanımlama, Mevzuat, Firma Altyapısı Eşleştirme,
Akıllı Başlangıç Reçetesi."""
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.infrastructure import ProductionLine
from app.models.recipe import PackagingRequest
from app.schemas.infrastructure import LineMatchCriteriaOut, LineMatchOut, ProductionLineOut
from app.schemas.recipe import (
    PackagingRequestCreate,
    PackagingRequestOut,
    RecipeOut,
    RegulatoryAssessmentOut,
    RegulatoryAssessmentSummaryOut,
    SpecExtractionOut,
)
from app.services import packaging_service

router = APIRouter(prefix="/packaging-flow", tags=["Aşama 2-5 - Ambalaj & Mevzuat & Eşleştirme"])


def _get_request_or_404(db: Session, request_id: str) -> PackagingRequest:
    req = db.get(PackagingRequest, request_id)
    if req is None:
        raise HTTPException(404, "Ambalaj talebi bulunamadı")
    return req


# --- Aşama 2 ---------------------------------------------------------------

@router.post("/requests", response_model=PackagingRequestOut)
def create_request(payload: PackagingRequestCreate, db: Session = Depends(get_db)):
    return packaging_service.create_packaging_request(db, payload.model_dump())


@router.get("/requests/{request_id}", response_model=PackagingRequestOut)
def get_request(request_id: str, db: Session = Depends(get_db)):
    return _get_request_or_404(db, request_id)


@router.put("/requests/{request_id}", response_model=PackagingRequestOut)
def update_request(request_id: str, payload: PackagingRequestCreate, db: Session = Depends(get_db)):
    req = _get_request_or_404(db, request_id)
    return packaging_service.update_packaging_request(db, req, payload.model_dump())


@router.post("/requests/{request_id}/spec-extraction", response_model=SpecExtractionOut)
async def upload_spec(
    request_id: str,
    file: UploadFile | None = None,
    spec_text: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    req = _get_request_or_404(db, request_id)
    text = spec_text or ""
    file_name = None
    if file is not None:
        file_name = file.filename
        raw = await file.read()
        if file.filename and file.filename.lower().endswith(".pdf"):
            text = _extract_pdf_text(raw)
        else:
            text = raw.decode("utf-8", errors="ignore")
    if not text.strip():
        raise HTTPException(400, "spec_text veya bir dosya (file) gönderilmeli")
    extracted = packaging_service.extract_spec(db, req, text, file_name)
    return SpecExtractionOut(**extracted)


def _extract_pdf_text(raw: bytes) -> str:
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# --- Aşama 3 -----------------------------------------------------------------

@router.post("/requests/{request_id}/regulatory-assessment", response_model=RegulatoryAssessmentSummaryOut)
def run_regulatory_assessment(request_id: str, db: Session = Depends(get_db)):
    req = _get_request_or_404(db, request_id)
    overall, assessments = packaging_service.assess_regulations(db, req)
    return RegulatoryAssessmentSummaryOut(
        overall_verdict=overall,
        assessments=[RegulatoryAssessmentOut.model_validate(a) for a in assessments],
        evidence_checklist=packaging_service.build_food_contact_evidence_checklist(db, req),
    )


# --- Aşama 4 -----------------------------------------------------------------

@router.get("/requests/{request_id}/infrastructure-matches", response_model=list[LineMatchOut])
def get_infrastructure_matches(request_id: str, db: Session = Depends(get_db)):
    req = _get_request_or_404(db, request_id)
    matches = packaging_service.match_infrastructure(db, req)
    return [
        LineMatchOut(
            line=ProductionLineOut.model_validate(m["line"]),
            compatible_material_ids=m["compatible_material_ids"],
            match_reason=m["match_reason"],
            eligible=m["eligible"],
            score_pct=m["score_pct"],
            criteria=LineMatchCriteriaOut(**m["criteria"]),
            missing=m["missing"],
        )
        for m in matches
    ]


# --- Aşama 5 -----------------------------------------------------------------

@router.post("/requests/{request_id}/initial-recipe", response_model=RecipeOut)
def generate_initial_recipe(request_id: str, line_id: str, db: Session = Depends(get_db)):
    req = _get_request_or_404(db, request_id)
    line = db.get(ProductionLine, line_id)
    if line is None:
        raise HTTPException(404, "Üretim hattı bulunamadı")
    try:
        recipe = packaging_service.generate_initial_recipe(db, req, line)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return recipe
