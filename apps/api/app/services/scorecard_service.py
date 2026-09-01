"""Faz O.2 (Madde 19) — Sürdürülebilirlik Karnesi: 9 boyutta çok yönlü bir
özet. HİÇBİR yeni hesap YOK -- her boyut, `report_service.
build_optimization_report_data()`'nın zaten hesapladığı `comparison`
(production_flow_service.build_comparison) ve `executive_summary`
(report_service.build_executive_summary) içindeki GERÇEK sayılardan
türetilir (aynı hesap iki kez YAPILMAZ). Referans yoksa azaltım/karşılaştırma
yüzdesi UYDURULMAZ -- `has_reference=False` ile mutlak durum gösterilir (Faz
A kuralı). `veri_guveni_kind` alanı HAM bir kaynak "kind" string'idir (ör.
"hesaplanan"/"mevzuat"/"simulasyon_verisi") -- YENİ bir güven eşleme mantığı
KURULMAZ, çağıran taraf bunu KENDİ mevcut sözlüğüyle çözer: backend PDF'te
`report_service.data_confidence_level()`, frontend'de
`labels.ts::dataConfidenceFromSourceKind()`."""
from sqlalchemy.orm import Session

from app.models.knowledge import Regulation
from app.models.recipe import Recipe, RegulatoryAssessment
from app.services.packaging_service import build_food_contact_evidence_checklist


def _dim(
    key: str,
    label: str,
    deger: float | None = None,
    birim: str | None = None,
    durum_metni: str | None = None,
    has_reference: bool = False,
    karsilastirma_pct: float | None = None,
    veri_guveni_kind: str | None = None,
) -> dict:
    return {
        "key": key,
        "label": label,
        "deger": deger,
        "birim": birim,
        "durum_metni": durum_metni,
        "has_reference": has_reference,
        "karsilastirma_pct": karsilastirma_pct,
        "veri_guveni_kind": veri_guveni_kind,
    }


def _malzeme_verimliligi(per_1000: dict | None) -> dict:
    if per_1000 is None:
        return _dim("malzeme_verimliligi", "Malzeme Verimliliği", durum_metni="henuz_uretilmedi")
    virgin, pcr, regranul, fire = (per_1000.get(k) for k in ("virgin_kg", "pcr_kg", "regranul_kg", "fire_kg"))
    if None in (virgin, pcr, regranul, fire):
        return _dim("malzeme_verimliligi", "Malzeme Verimliliği", durum_metni="kutle_verisi_eksik")
    urun_kg = virgin + pcr + regranul
    girdi_kg = urun_kg + fire
    verimlilik_pct = round((urun_kg / girdi_kg) * 100, 1) if girdi_kg > 0 else None
    return _dim(
        "malzeme_verimliligi", "Malzeme Verimliliği", deger=verimlilik_pct, birim="%",
        veri_guveni_kind=per_1000.get("fire_enerji_veri_kaynagi"),
    )


def _dongusellik(db: Session, recipe: Recipe) -> dict:
    if recipe.packaging_request_id is None:
        return _dim("dongusellik", "Döngüsellik", durum_metni="degerlendirilmedi")
    assessment = (
        db.query(RegulatoryAssessment)
        .join(Regulation, RegulatoryAssessment.regulation_id == Regulation.id)
        .filter(RegulatoryAssessment.packaging_request_id == recipe.packaging_request_id, Regulation.code == "PPWR-ART-6")
        .first()
    )
    if assessment is None:
        return _dim("dongusellik", "Döngüsellik", durum_metni="degerlendirilmedi")
    return _dim("dongusellik", "Döngüsellik", durum_metni=assessment.verdict, veri_guveni_kind="mevzuat")


def _virgin_azaltimi(comparison: dict, gains: dict | None, has_reference: bool) -> dict:
    return _dim(
        "virgin_azaltimi", "Virgin Azaltımı", deger=comparison["recommended"]["virgin_pct"], birim="%",
        has_reference=has_reference,
        karsilastirma_pct=(gains or {}).get("virgin_azalimi_pct"),
        veri_guveni_kind="hesaplanan",
    )


def _pcr_kullanimi(comparison: dict, gains: dict | None, has_reference: bool) -> dict:
    return _dim(
        "pcr_kullanimi", "PCR Kullanımı", deger=comparison["recommended"]["pcr_pct"], birim="%",
        has_reference=has_reference,
        karsilastirma_pct=(gains or {}).get("pcr_artisi_pct"),
        veri_guveni_kind="hesaplanan",
    )


def _karbon_performansi(per_1000: dict | None, gains: dict | None, has_reference: bool) -> dict:
    if per_1000 is None:
        return _dim("karbon_performansi", "Karbon Performansı", durum_metni="henuz_uretilmedi")
    return _dim(
        "karbon_performansi", "Karbon Performansı", deger=per_1000.get("karbon_kg_co2"), birim="kg CO2",
        has_reference=has_reference,
        karsilastirma_pct=(gains or {}).get("karbon_azaltimi_pct"),
        veri_guveni_kind=per_1000.get("karbon_veri_kalitesi"),
    )


def _enerji_performansi(per_1000: dict | None, gains: dict | None, has_reference: bool) -> dict:
    if per_1000 is None:
        return _dim("enerji_performansi", "Enerji Performansı", durum_metni="henuz_uretilmedi")
    return _dim(
        "enerji_performansi", "Enerji Performansı", deger=per_1000.get("enerji_kwh"), birim="kWh",
        has_reference=has_reference,
        karsilastirma_pct=(gains or {}).get("enerji_azaltimi_pct"),
        veri_guveni_kind=per_1000.get("fire_enerji_veri_kaynagi"),
    )


def _fire_performansi(per_1000: dict | None, gains: dict | None, has_reference: bool) -> dict:
    if per_1000 is None:
        return _dim("fire_performansi", "Fire Performansı", durum_metni="henuz_uretilmedi")
    return _dim(
        "fire_performansi", "Fire Performansı", deger=per_1000.get("fire_kg"), birim="kg",
        has_reference=has_reference,
        karsilastirma_pct=(gains or {}).get("fire_azaltimi_pct"),
        veri_guveni_kind=per_1000.get("fire_enerji_veri_kaynagi"),
    )


def _mevzuat_hazirligi(db: Session, recipe: Recipe) -> dict:
    if recipe.packaging_request_id is None:
        return _dim("mevzuat_hazirligi", "Mevzuat Hazırlığı", durum_metni="degerlendirilmedi")
    assessments = (
        db.query(RegulatoryAssessment).filter_by(packaging_request_id=recipe.packaging_request_id).all()
    )
    if not assessments:
        return _dim("mevzuat_hazirligi", "Mevzuat Hazırlığı", durum_metni="degerlendirilmedi")
    uygun = sum(1 for a in assessments if a.verdict == "uygun_gorunuyor")
    toplam = len(assessments)
    return _dim(
        "mevzuat_hazirligi", "Mevzuat Hazırlığı", deger=round((uygun / toplam) * 100, 1), birim="%",
        durum_metni=f"{uygun}/{toplam} madde uygun görünüyor", veri_guveni_kind="mevzuat",
    )


def _kanit_tamamlanma(db: Session, recipe: Recipe) -> dict:
    if recipe.packaging_request is None:
        return _dim("kanit_tamamlanma", "Kanıt Tamamlanma", durum_metni="degerlendirilmedi")
    checklist = build_food_contact_evidence_checklist(db, recipe.packaging_request)
    if not checklist:
        return _dim("kanit_tamamlanma", "Kanıt Tamamlanma", durum_metni="gida_temasi_yok")
    mevcut = sum(1 for i in checklist if i["status"] == "mevcut")
    gerekli = sum(1 for i in checklist if i["status"] != "gerekli_degil")
    tamamlanma_pct = round((mevcut / gerekli) * 100, 1) if gerekli > 0 else None
    return _dim(
        "kanit_tamamlanma", "Kanıt Tamamlanma", deger=tamamlanma_pct, birim="%",
        durum_metni=f"{mevcut}/{gerekli} kanıt mevcut",
    )


def build_sustainability_scorecard(db: Session, recipe: Recipe, comparison: dict, executive_summary: dict) -> dict:
    per_1000 = executive_summary["realized_absolute_per_1000_units"]
    gains = executive_summary["gains_pct"]
    has_reference = executive_summary["has_reference"]

    dimensions = [
        _malzeme_verimliligi(per_1000),
        _dongusellik(db, recipe),
        _virgin_azaltimi(comparison, gains, has_reference),
        _pcr_kullanimi(comparison, gains, has_reference),
        _karbon_performansi(per_1000, gains, has_reference),
        _enerji_performansi(per_1000, gains, has_reference),
        _fire_performansi(per_1000, gains, has_reference),
        _mevzuat_hazirligi(db, recipe),
        _kanit_tamamlanma(db, recipe),
    ]
    return {"dimensions": dimensions}
