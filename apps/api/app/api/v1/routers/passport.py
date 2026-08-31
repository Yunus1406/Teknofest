"""Faz C.1/C.2 — Dijital Ürün Pasaportu. `POST /passports` oluşturur/getirir
(idempotent, her zaman sadece public içerik — oluşturma anında ticari sır
sızdırılmaz). `GET /passports/{passport_no}` QR'ın hedeflediği genel
sayfanın verisidir; `authorized_key` doğru geldiğinde authorized alanı da
dolar, aksi halde sessizce None kalır (bkz. app/services/passport_service.py
modül docstring'i — bu gerçek bir auth sistemi değildir, MVP kapsamıdır)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.digital_product_passport import DigitalProductPassport
from app.schemas.passport import DigitalProductPassportOut
from app.services.passport_service import build_passport_content, get_or_create_passport

router = APIRouter(prefix="/passports", tags=["Dijital Ürün Pasaportu"])


class PassportCreateIn(BaseModel):
    recipe_id: str


def _authorized(authorized_key: str | None) -> bool:
    configured = get_settings().dpp_authorized_key
    return bool(configured) and authorized_key == configured


@router.post("", response_model=DigitalProductPassportOut)
def create_or_get_passport(payload: PassportCreateIn, db: Session = Depends(get_db)):
    try:
        passport = get_or_create_passport(db, payload.recipe_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return build_passport_content(db, passport, include_authorized=False)


@router.get("/{passport_no}", response_model=DigitalProductPassportOut)
def get_passport(passport_no: str, authorized_key: str | None = None, db: Session = Depends(get_db)):
    passport = db.query(DigitalProductPassport).filter_by(passport_no=passport_no).one_or_none()
    if passport is None:
        raise HTTPException(404, "Pasaport bulunamadı")
    return build_passport_content(db, passport, include_authorized=_authorized(authorized_key))
