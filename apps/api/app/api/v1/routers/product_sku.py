"""Ürün/SKU Kütüphanesi — Firma Gerçek Veri Kütüphanesi'ndeki kalıcı ürün
kimlikleri. Aşama 2'deki bir talep (PackagingRequest) opsiyonel olarak bir
SKU'yu hedefleyebilir (bkz. PackagingRequestCreate.sku_id)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.product_sku import ProductSku
from app.schemas.product_sku import ProductSkuCreate, ProductSkuDetailOut, ProductSkuOut, ProductSkuUpdate
from app.services.traceability_service import build_recipe_traceability

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


@router.get("/{sku_id}/detail", response_model=ProductSkuDetailOut)
def get_product_sku_detail(sku_id: str, db: Session = Depends(get_db)):
    """SKU alanları + (varsa) `current_recipe_id` üzerinden tam izlenebilirlik
    zinciri -- Faz B.9'daki `build_recipe_traceability` yeniden kullanılır,
    zincir mantığı burada tekrar kurulmaz."""
    sku = db.get(ProductSku, sku_id)
    if sku is None:
        raise HTTPException(404, "SKU bulunamadı")
    trace = build_recipe_traceability(db, sku.current_recipe_id) if sku.current_recipe_id else None
    return ProductSkuDetailOut(**ProductSkuOut.model_validate(sku).model_dump(), traceability=trace)


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


@router.put("/{sku_id}", response_model=ProductSkuOut)
def update_product_sku(sku_id: str, payload: ProductSkuUpdate, db: Session = Depends(get_db)):
    sku = db.get(ProductSku, sku_id)
    if sku is None:
        raise HTTPException(404, "SKU bulunamadı")
    updates = payload.model_dump(exclude_unset=True)
    new_code = updates.get("sku_code")
    if new_code is not None and new_code != sku.sku_code:
        existing = db.query(ProductSku).filter_by(sku_code=new_code).one_or_none()
        if existing is not None:
            raise HTTPException(400, f"SKU kodu '{new_code}' zaten kullanımda")
    for field, value in updates.items():
        setattr(sku, field, value)
    db.commit()
    db.refresh(sku)
    return sku
