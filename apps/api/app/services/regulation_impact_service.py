"""Faz L.4 (Madde 17) — Mevzuat Değişiklik Etki Analizi. Bir mevzuat kaydı
güncellendiğinde (Faz L.3'ün versiyon geçmişi tetiklendiğinde), sistem
sadece yeni metni kaydetmekle kalmaz — hangi ürünleri/SKU'ları etkilediğini
bulur. Faz E.4'ün Ürün/SKU Hafızası + firma hafızası (RegulatoryAssessment
geçmişi, `regulation_version_snapshot` -- bkz. packaging_service.py Faz
L.3) taranır."""
from sqlalchemy.orm import Session

from app.models.enums import RegulatoryVerdict
from app.models.knowledge import Regulation
from app.models.product_sku import ProductSku
from app.models.recipe import PackagingRequest, RegulatoryAssessment
from app.services.packaging_service import _current_requirement_version


def analyze_regulation_change_impact(db: Session, regulation_code: str) -> dict:
    """"Aktif SKU" = en az bir `PackagingRequest`i olan `ProductSku` satırı
    (bu sistemde SKU'lar üzerinde ayrı bir "aktif/pasif" bayrağı yok --
    gerçekten kullanılmış olmak "aktif"in dürüst tanımıdır). "Etkilenen" =
    SKU'nun bu mevzuata ait EN AZ BİR `RegulatoryAssessment`'ı, GÜNCEL
    versiyondan FARKLI bir `regulation_version_snapshot` taşıyor (Faz L.3).
    "Yeni kanıt gerekli" = etkilenen VE en son verdict `uygun_gorunuyor`
    DEĞİL. "Reçete yeniden değerlendirilmeli" = etkilenen VE SKU'nun
    doğrulanmış (`current_recipe_id` dolu) bir reçetesi var."""
    reg = db.query(Regulation).filter_by(code=regulation_code).one_or_none()
    if reg is None:
        raise ValueError(f"'{regulation_code}' kodlu mevzuat bulunamadı.")

    current_version = _current_requirement_version(db, reg.id)

    active_skus = (
        db.query(ProductSku)
        .join(PackagingRequest, PackagingRequest.sku_id == ProductSku.id)
        .distinct()
        .all()
    )

    affected: list[ProductSku] = []
    evidence_needed: list[ProductSku] = []
    recipe_reassessment: list[ProductSku] = []

    for sku in active_skus:
        assessments = (
            db.query(RegulatoryAssessment)
            .join(PackagingRequest, RegulatoryAssessment.packaging_request_id == PackagingRequest.id)
            .filter(PackagingRequest.sku_id == sku.id, RegulatoryAssessment.regulation_id == reg.id)
            .all()
        )
        if not assessments:
            continue
        is_affected = any(
            a.regulation_version_snapshot is not None and a.regulation_version_snapshot != current_version
            for a in assessments
        )
        if not is_affected:
            continue
        affected.append(sku)

        latest = max(assessments, key=lambda a: a.created_at)
        if latest.verdict != RegulatoryVerdict.OK.value:
            evidence_needed.append(sku)
        if sku.current_recipe_id is not None:
            recipe_reassessment.append(sku)

    return {
        "regulation_code": regulation_code,
        "current_version": current_version,
        "total_active_skus": len(active_skus),
        "affected_sku_count": len(affected),
        "evidence_needed_count": len(evidence_needed),
        "recipe_reassessment_count": len(recipe_reassessment),
        "affected_sku_codes": sorted(s.sku_code for s in affected),
    }
