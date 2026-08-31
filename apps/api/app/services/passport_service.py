"""Dijital Ürün Pasaportu — Faz C.1: kimlik+versiyon yönetimi (`passport_no`
üretimi, Rev.1->Rev.2 zinciri). Faz C.2: içerik derleme + public/authorized
ayrımı + QR üretimi.

İçerik ASLA burada dondurulmuş bir kopya olarak saklanmaz — her çağrıda
ilgili reçeteden/servislerden CANLI derlenir (Faz A/B'nin 'tek doğruluk
kaynağı' ilkesi). Public/authorized ayrımı Yetkili Alan (ticari hammadde
grade/lot/tedarikçi + tam izlenebilirlik zinciri + ham mevzuat gerekçe
metinleri) için basit bir paylaşılan-anahtar (`Settings.dpp_authorized_key`)
ile kontrol edilir — bu GERÇEK bir kullanıcı/oturum sistemi DEĞİLDİR, MVP
kapsamı: anahtar yanlış/eksikse authorized alan sessizce None kalır (hata
fırlatmaz, 'bu veri var ama gizli' sinyali sızdırmaz)."""
import base64
from datetime import datetime, timezone
from io import BytesIO

import qrcode
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.company import Facility
from app.models.digital_product_passport import DigitalProductPassport
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Regulation
from app.models.production import PhysicalTest, ProductionOrder, SustainabilityResult
from app.models.recipe import Recipe, RegulatoryAssessment
from app.models.regulation_requirement import RegulationRequirement
from app.services import production_flow_service, traceability_service


def _next_passport_no(db: Session) -> str:
    """Format: DPP-{yıl}-{6 haneli sıra}. Yıl bazlı sayaç — MVP kapsamı:
    eşzamanlı yarış durumuna karşı korumasız (tek kiracılı demo ortamı için
    kabul edilebilir; çok kullanıcılı üretimde DB seviyesinde bir sequence/
    advisory lock'a taşınmalı)."""
    year = datetime.now(timezone.utc).year
    prefix = f"DPP-{year}-"
    count = (
        db.query(func.count(DigitalProductPassport.id))
        .filter(DigitalProductPassport.passport_no.like(f"{prefix}%"))
        .scalar()
    )
    return f"{prefix}{count + 1:06d}"


def _group_key(recipe: Recipe) -> tuple[str, str]:
    """Aynı ürün/reçete soyunu (Rev.1->Rev.2 zinciri) gruplamak için: SKU
    varsa onunla, yoksa (SKU'suz tek seferlik talepler için bile revizyon
    zinciri kurulabilsin diye) packaging_request_id ile."""
    if recipe.packaging_request is not None and recipe.packaging_request.sku_id:
        return ("sku", recipe.packaging_request.sku_id)
    return ("packaging_request", recipe.packaging_request_id)


def _latest_passport_for_group(db: Session, group_key: tuple[str, str]) -> DigitalProductPassport | None:
    kind, value = group_key
    query = db.query(DigitalProductPassport).join(Recipe, DigitalProductPassport.recipe_id == Recipe.id)
    if kind == "sku":
        query = query.filter(DigitalProductPassport.sku_id == value)
    else:
        query = query.filter(Recipe.packaging_request_id == value)
    return query.order_by(DigitalProductPassport.revision.desc()).first()


def get_or_create_passport(db: Session, recipe_id: str) -> DigitalProductPassport:
    """Bu reçete için zaten bir pasaport varsa onu döner (idempotent —
    butona tekrar basmak yeni bir revizyon AÇMAZ). Yoksa, aynı ürün/reçete
    soyunun en son revizyonunu bulup bir sonraki revizyonu oluşturur.
    Sadece `recipe.is_verified=True` reçeteler için çağrılabilir."""
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise ValueError("Reçete bulunamadı")
    if not recipe.is_verified:
        raise ValueError(
            "Sadece doğrulanmış reçeteler için Dijital Ürün Pasaportu oluşturulabilir"
        )

    existing = db.query(DigitalProductPassport).filter_by(recipe_id=recipe.id).one_or_none()
    if existing is not None:
        return existing

    group_key = _group_key(recipe)
    previous = _latest_passport_for_group(db, group_key)
    revision = (previous.revision + 1) if previous is not None else 1

    passport = DigitalProductPassport(
        passport_no=_next_passport_no(db),
        recipe_id=recipe.id,
        sku_id=recipe.packaging_request.sku_id if recipe.packaging_request is not None else None,
        revision=revision,
        previous_passport_id=previous.id if previous is not None else None,
    )
    db.add(passport)
    db.commit()
    db.refresh(passport)
    return passport


# --- Faz C.2: içerik derleme + QR + public/authorized ayrımı --------------

def _production_date_for_recipe(db: Session, recipe: Recipe) -> datetime | None:
    """Gerçek bir üretim emri varsa onun bitiş/başlangıç zamanı; yoksa
    (henüz üretime geçmemiş ama doğrulanmış — nadir ama mümkün) sürdürüle-
    bilirlik sonucunun ya da reçetenin son güncellenme zamanı — asla
    uydurma bir tarih üretilmez, her zaman gerçek bir DB zaman damgası."""
    latest_order = (
        db.query(ProductionOrder)
        .filter_by(recipe_id=recipe.id)
        .order_by(ProductionOrder.created_at.desc())
        .first()
    )
    if latest_order is not None:
        return latest_order.actual_end or latest_order.actual_start or latest_order.created_at

    latest_result = (
        db.query(SustainabilityResult)
        .filter_by(recipe_id=recipe.id, is_actual=True)
        .order_by(SustainabilityResult.created_at.desc())
        .first()
    )
    if latest_result is not None:
        return latest_result.created_at
    return recipe.updated_at


def _layer_structure_pattern(recipe: Recipe) -> tuple[str | None, int]:
    by_index = {layer.layer_index: layer.layer_label for layer in recipe.layers}
    if not by_index:
        return None, 0
    ordered = [by_index[i] for i in sorted(by_index)]
    return "/".join(ordered), len(ordered)


def _qr_data_uri(target_url: str) -> str:
    img = qrcode.make(target_url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _status_summary(
    recipe: Recipe,
    physical_tests: list[PhysicalTest],
    regulatory_assessments: list[RegulatoryAssessment],
    trace: dict,
    passport: DigitalProductPassport,
) -> dict:
    # Faz D.2 — 3 durum: beklemede (kriter/ölçüm tanımsız) ASLA "Başarısız"
    # ile karıştırılmaz. `passport_service.get_or_create_passport` zaten
    # sadece `recipe.is_verified=True` reçeteler için çağrılabildiğinden (ve
    # bu artık finalize_result'ın kendisi TÜM testler basarili değilse
    # reddettiği için) burası pratikte hep "Doğrulandı" olur — yine de
    # mantık kendi başına doğru olmalı, is_verified'a körü körüne güvenmez.
    if not physical_tests:
        physical_performance = "Beklemede"
    elif any(t.result == "basarisiz" for t in physical_tests):
        physical_performance = "Başarısız"
    elif any(t.result == "beklemede" for t in physical_tests):
        physical_performance = "Doğrulama Bekleniyor"
    else:
        physical_performance = "Doğrulandı"

    chain_complete = bool(
        trace.get("company") and trace.get("facility") and trace.get("machine") and trace.get("layers")
    )

    return {
        "digital_identity": "Aktif",
        "recipe_status": "Doğrulandı" if recipe.is_verified else "Beklemede",
        "physical_performance": physical_performance,
        "data_traceability": "Tam" if chain_complete else "Kısmi",
        "ppwr_status": (
            "Ön Uyum Değerlendirmesi Tamamlandı"
            if regulatory_assessments
            else "Değerlendirme Bekleniyor"
        ),
        "last_updated": passport.updated_at.isoformat(),
    }


_REGULATORY_DISCLAIMER = (
    "Bu bölüm mevzuat ön uyum değerlendirmesidir; hukuki uygunluk "
    "sertifikasyonu değildir."
)


def build_passport_content(db: Session, passport: DigitalProductPassport, include_authorized: bool) -> dict:
    """`include_authorized=True` SADECE çağıran (router) doğru
    `dpp_authorized_key`'i doğruladıysa geçirilmeli — bu fonksiyon kendi
    başına anahtar kontrolü yapmaz (o sorumluluk router'da), burada sadece
    içerik derlenir."""
    recipe = db.get(Recipe, passport.recipe_id)
    packaging_request = recipe.packaging_request
    sku = packaging_request.sku if packaging_request is not None and packaging_request.sku_id else None

    line = db.get(ProductionLine, recipe.line_id) if recipe.line_id else None
    facility = db.get(Facility, line.facility_id) if line is not None and line.facility_id else None
    company = facility.company if facility is not None else None

    comparison = production_flow_service.build_comparison(db, recipe)
    recommended = comparison["recommended"]
    gains = comparison["gains"]

    layer_structure, layer_count = _layer_structure_pattern(recipe)
    polymers = sorted({layer.material.polymer.code for layer in recipe.layers if layer.material is not None})

    sustainability_row = (
        db.query(SustainabilityResult)
        .filter_by(recipe_id=recipe.id, is_actual=True)
        .order_by(SustainabilityResult.created_at.desc())
        .first()
    )
    per_1000_units = sustainability_row.per_1000_units if sustainability_row is not None else None

    physical_tests = db.query(PhysicalTest).filter_by(recipe_id=recipe.id).all()

    regulatory_assessments: list[RegulatoryAssessment] = []
    if packaging_request is not None:
        regulatory_assessments = (
            db.query(RegulatoryAssessment).filter_by(packaging_request_id=packaging_request.id).all()
        )
    regulatory_public = []
    regulatory_reasoning = []
    for a in regulatory_assessments:
        reg = db.get(Regulation, a.regulation_id)
        requirement = (
            db.query(RegulationRequirement).filter_by(regulation_id=a.regulation_id).first()
            if reg is not None
            else None
        )
        regulatory_public.append(
            {
                "regulation_code": reg.code if reg is not None else None,
                "article": requirement.article if requirement is not None else None,
                "verdict": a.verdict,
            }
        )
        regulatory_reasoning.append(
            {"regulation_code": reg.code if reg is not None else None, "reasoning": a.reasoning}
        )

    trace = traceability_service.build_recipe_traceability(db, recipe.id) or {}
    version_history = production_flow_service.version_history(db, recipe)
    production_date = _production_date_for_recipe(db, recipe)

    public = {
        "header": {
            "passport_no": passport.passport_no,
            "revision": passport.revision,
            "sku_code": sku.sku_code if sku is not None else None,
            "product_name": sku.product_name if sku is not None else None,
            "recipe_id": recipe.id,
            "recipe_version": recipe.version,
            "facility_name": facility.name if facility is not None else None,
            "company_name": company.name if company is not None else None,
            "production_date": production_date.isoformat() if production_date else None,
            "line_name": line.name if line is not None else None,
            "packaging_type": packaging_request.packaging_type if packaging_request is not None else None,
            "target_market": packaging_request.target_market if packaging_request is not None else None,
        },
        "status_summary": _status_summary(recipe, physical_tests, regulatory_assessments, trace, passport),
        "material_summary": {
            "total_gsm": recipe.total_gsm,
            "total_micron": recipe.total_micron,
            "layer_count": layer_count,
            "layer_structure": layer_structure,
            "polymers": polymers,
            "virgin_pct": recommended["virgin_pct"],
            "pcr_pct": recommended["pcr_pct"],
            "regranule_pct": recommended["regranule_pct"],
        },
        "environmental": {
            "per_1000_units": per_1000_units,
            "gains_pct": gains,
            "has_reference": comparison["reference"] is not None,
        },
        "physical_tests": [
            {
                "test_type": t.test_type,
                "value": t.value,
                "unit": t.unit,
                "target_min": t.target_min,
                "target_max": t.target_max,
                "test_method": t.test_method,
                "result": t.result,
                "passed": t.passed,
            }
            for t in physical_tests
        ],
        "regulatory": regulatory_public,
        "regulatory_disclaimer": _REGULATORY_DISCLAIMER,
        "version_history": [
            {
                "id": v["id"],
                "version": v["version"],
                "status": v["status"],
                "is_verified": v["is_verified"],
                "created_at": v["created_at"].isoformat() if hasattr(v["created_at"], "isoformat") else v["created_at"],
            }
            for v in version_history
        ],
    }

    authorized = None
    if include_authorized:
        layer_materials = [
            {
                "layer_index": layer.layer_index,
                "layer_label": layer.layer_label,
                "material_name": layer.material.name if layer.material is not None else None,
                "material_type": layer.material.material_type if layer.material is not None else None,
                "manufacturer": layer.material.manufacturer if layer.material is not None else None,
                "supplier": layer.material.supplier if layer.material is not None else None,
                "lot_number": layer.material.lot_number if layer.material is not None else None,
                "certification_status": (
                    layer.material.certification_status if layer.material is not None else None
                ),
                "ratio_pct": layer.ratio_pct,
            }
            for layer in sorted(recipe.layers, key=lambda l: l.layer_index)
        ]
        authorized = {
            "layer_materials": layer_materials,
            "traceability": trace,
            "regulatory_reasoning": regulatory_reasoning,
        }

    settings = get_settings()
    qr_target = f"{settings.public_web_base_url}/dpp/{passport.passport_no}"

    return {
        "public": public,
        "authorized": authorized,
        "qr_code_data_uri": _qr_data_uri(qr_target),
    }
