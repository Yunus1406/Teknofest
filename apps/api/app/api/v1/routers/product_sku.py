"""Ürün/SKU Kütüphanesi — Firma Gerçek Veri Kütüphanesi'ndeki kalıcı ürün
kimlikleri. Aşama 2'deki bir talep (PackagingRequest) opsiyonel olarak bir
SKU'yu hedefleyebilir (bkz. PackagingRequestCreate.sku_id)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.product_sku import ProductSku
from app.schemas.product_sku import ProductSkuCreate, ProductSkuOut

router = APIRouter(prefix="/product-skus", tags=["Ürün/SKU Kütüphanesi"])


@router.get("", response_model=list[ProductSkuOut])
def list_product_skus(db: Session = Depends(get_db)):
    return db.query(ProductSku).all()


@router.get("/{sku_id}", response_model=ProductSkuOut)
def get_product_sku(sku_id: str, db: Session = Depends(get_db)):
    sku = db.get(ProductSku, sku_id)
    if sku is None:
        raise HTTPException(404, "SKU bulunamadı")
    return sku


@router.post("", response_model=ProductSkuOut)
def create_product_sku(payload: ProductSkuCreate, db: Session = Depends(get_db)):
    existing = db.query(ProductSku).filter_by(sku_code=payload.sku_code).one_or_none()
    if existing is not None:
        raise HTTPException(400, f"SKU kodu '{payload.sku_code}' zaten kullanımda")
    sku = ProductSku(**payload.model_dump())
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return sku
