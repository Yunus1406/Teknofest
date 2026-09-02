"""Faz R.2 (Madde 27) — Dijital Uygunluk Dosyası. Yeni bir DB alanı/tablo
YOK -- SKU'nun `current_recipe_id`'si üzerinden MEVCUT servislerin (L.2/L.3/
L.4/F.1/R.3) sonuçları tek, SKU-seviyeli bir görünümde AGREGE edilir. Her
kalem GERÇEK veriden ✓ (tamam) / ⚠ (kismi) / ✕ (eksik) durumuna çevrilir --
hiçbir kalem, veri yoksa "tamam" gibi gösterilmez; dürüstçe "eksik" kalır.

Her kalem SKU'nun `current_recipe_id`'si (varsa) üzerinden hesaplanır. SKU'nun
hiç doğrulanmış reçetesi yoksa (current_recipe_id None) çoğu kalem dürüstçe
"eksik" döner -- bu bir hata durumu DEĞİL, sadece henüz üretim/değerlendirme
geçmişi olmadığı anlamına gelir (bkz. ProductSkuDetailOut docstring, Faz B.9
ile aynı disiplin)."""
from sqlalchemy.orm import Session

from app.models.enums import PhysicalTestResult, ProductionOrderStatus, RegulatoryVerdict
from app.models.knowledge import Regulation
from app.models.product_sku import ProductSku
from app.models.production import PhysicalTest, ProductionOrder
from app.models.recipe import PackagingRequest, Recipe, RegulatoryAssessment
from app.services.carbon import resolve_carbon_ef, status_label, worst_status
from app.services.packaging_service import _current_requirement_version, build_food_contact_evidence_checklist
from app.services.report_service import _regulation_version_history_section
from app.services.supplier_risk_service import build_supplier_evidence_radar


def _item(key: str, title: str, durum: str, aciklama: str) -> dict:
    return {"key": key, "title": title, "durum": durum, "aciklama": aciklama}


def _urun_tanimi_item(sku: ProductSku) -> dict:
    fields = [sku.dimensions, sku.film_thickness_micron, sku.gsm, sku.layer_count, sku.layer_structure, sku.technical_spec_ref]
    dolu = sum(1 for f in fields if f not in (None, {}, ""))
    durum = "tamam" if dolu == len(fields) else "eksik" if dolu == 0 else "kismi"
    return _item(
        "urun_tanimi", "Ürün Tanımı", durum,
        f"{dolu}/{len(fields)} tanımlayıcı alan dolu (boyutlar, kalınlık, gramaj, katman sayısı/yapısı, teknik şartname referansı).",
    )


def _recete_item(recipe: Recipe | None) -> dict:
    if recipe is None:
        return _item("recete", "Reçete", "eksik", "Bu SKU'ya bağlı bir reçete yok.")
    if not recipe.is_verified:
        return _item("recete", "Reçete", "kismi", f"Reçete V{recipe.version} var ancak henüz doğrulanmadı.")
    return _item("recete", "Reçete", "tamam", f"Doğrulanmış Reçete V{recipe.version}.")


def _hammadde_item(materials: list) -> dict:
    if not materials:
        return _item("hammadde", "Hammadde", "eksik", "Reçeteye bağlı hammadde katmanı yok.")
    dolu = sum(1 for m in materials if m.technical_datasheet_ref is not None)
    durum = "tamam" if dolu == len(materials) else "eksik" if dolu == 0 else "kismi"
    return _item(
        "hammadde", "Hammadde", durum,
        f"{dolu}/{len(materials)} katman malzemesinin teknik veri föyü referansı var.",
    )


def _tedarikci_belgeleri_item(materials: list) -> dict:
    if not materials:
        return _item("tedarikci_belgeleri", "Tedarikçi Belgeleri", "eksik", "Reçeteye bağlı hammadde yok.")
    radarlar = [build_supplier_evidence_radar(m) for m in materials]
    ortalama = round(sum(r["tamlik_pct"] for r in radarlar) / len(radarlar), 1)
    durum = "tamam" if ortalama >= 80 else "eksik" if ortalama < 40 else "kismi"
    return _item(
        "tedarikci_belgeleri", "Tedarikçi Belgeleri", durum,
        f"Hammadde tedarikçi kanıt tamlığı ortalaması %{ortalama} (bkz. R.3 tedarikçi risk radarı).",
    )


def _ppwr_kontrolleri_item(db: Session, req: PackagingRequest | None) -> dict:
    if req is None:
        return _item("ppwr_kontrolleri", "PPWR Kontrolleri", "eksik", "Bu SKU için bir teknik şartname/mevzuat değerlendirmesi yok.")
    assessments = (
        db.query(RegulatoryAssessment)
        .join(Regulation, RegulatoryAssessment.regulation_id == Regulation.id)
        .filter(RegulatoryAssessment.packaging_request_id == req.id, Regulation.code.like("PPWR-%"))
        .all()
    )
    if not assessments:
        return _item("ppwr_kontrolleri", "PPWR Kontrolleri", "eksik", "PPWR maddeleri için değerlendirme kaydı yok.")
    if any(a.verdict == RegulatoryVerdict.NOT_OK for a in assessments):
        durum = "eksik"
    elif all(a.verdict == RegulatoryVerdict.OK for a in assessments):
        durum = "tamam"
    else:
        durum = "kismi"
    uygun = sum(1 for a in assessments if a.verdict == RegulatoryVerdict.OK)
    return _item(
        "ppwr_kontrolleri", "PPWR Kontrolleri", durum,
        f"{uygun}/{len(assessments)} PPWR maddesi 'uygun görünüyor' değerlendirildi.",
    )


def _gida_temas_item(db: Session, req: PackagingRequest | None) -> dict:
    if req is None:
        return _item("gida_temas_kontrolleri", "Gıda Temas Kontrolleri", "eksik", "Bu SKU için bir teknik şartname yok.")
    checklist = build_food_contact_evidence_checklist(db, req)
    if not checklist:
        return _item("gida_temas_kontrolleri", "Gıda Temas Kontrolleri", "tamam", "Gıda temaslı değil — kanıt kontrolü gerekmiyor.")
    tamam_sayisi = sum(1 for c in checklist if c["status"] == "tamam")
    durum = "tamam" if tamam_sayisi == len(checklist) else "eksik" if tamam_sayisi == 0 else "kismi"
    return _item(
        "gida_temas_kontrolleri", "Gıda Temas Kontrolleri", durum,
        f"{tamam_sayisi}/{len(checklist)} gıda temas kanıt kalemi mevcut.",
    )


def _testler_item(db: Session, recipe: Recipe | None) -> dict:
    if recipe is None:
        return _item("testler", "Testler", "eksik", "Reçete yok, fiziksel test yapılamaz.")
    tests = db.query(PhysicalTest).filter_by(recipe_id=recipe.id).all()
    if not tests:
        return _item("testler", "Testler", "eksik", "Fiziksel test kaydı yok.")
    basarisiz = sum(1 for t in tests if t.result == PhysicalTestResult.FAILED)
    beklemede = sum(1 for t in tests if t.result == PhysicalTestResult.PENDING)
    if basarisiz > 0:
        durum = "eksik"
    elif beklemede > 0:
        durum = "kismi"
    else:
        durum = "tamam"
    return _item(
        "testler", "Testler", durum,
        f"{len(tests)} test kaydı — {basarisiz} başarısız, {beklemede} beklemede.",
    )


def _karbon_hesabi_item(materials: list) -> dict:
    if not materials:
        return _item("karbon_hesabi", "Karbon Hesabı", "eksik", "Reçeteye bağlı hammadde yok.")
    en_kotu = worst_status([resolve_carbon_ef(m)[1] for m in materials])
    durum = {"tanimli_gercek": "tamam", "tanimli_demo": "kismi", "tanimlanmadi": "eksik"}[en_kotu]
    return _item("karbon_hesabi", "Karbon Hesabı", durum, status_label(en_kotu))


def _uretim_kayitlari_item(db: Session, recipe: Recipe | None) -> dict:
    if recipe is None:
        return _item("uretim_kayitlari", "Üretim Kayıtları", "eksik", "Reçete yok, üretim emri olamaz.")
    orders = db.query(ProductionOrder).filter_by(recipe_id=recipe.id).all()
    if not orders:
        return _item("uretim_kayitlari", "Üretim Kayıtları", "eksik", "Üretim emri kaydı yok.")
    tamamlanan = sum(1 for o in orders if o.status == ProductionOrderStatus.TAMAMLANDI)
    durum = "tamam" if tamamlanan > 0 else "kismi"
    return _item(
        "uretim_kayitlari", "Üretim Kayıtları", durum,
        f"{len(orders)} üretim emri — {tamamlanan} tamamlandı.",
    )


def _mevzuat_surumleri_item(db: Session, req: PackagingRequest | None) -> dict:
    if req is None:
        return _item("mevzuat_surumleri", "Mevzuat Sürümleri", "eksik", "Bu SKU için bir mevzuat değerlendirmesi yok.")
    assessments = db.query(RegulatoryAssessment).filter_by(packaging_request_id=req.id).all()
    if not assessments:
        return _item("mevzuat_surumleri", "Mevzuat Sürümleri", "eksik", "Değerlendirme kaydı yok.")
    guncel_disi = 0
    for a in assessments:
        current = _current_requirement_version(db, a.regulation_id)
        if a.regulation_version_snapshot is not None and current is not None and a.regulation_version_snapshot != current:
            guncel_disi += 1
    durum = "tamam" if guncel_disi == 0 else "eksik" if guncel_disi == len(assessments) else "kismi"
    return _item(
        "mevzuat_surumleri", "Mevzuat Sürümleri", durum,
        f"{len(assessments) - guncel_disi}/{len(assessments)} değerlendirme güncel mevzuat versiyonuyla uyumlu.",
    )


def _degisiklik_gecmisi_item(db: Session, req: PackagingRequest | None) -> dict:
    section = _regulation_version_history_section(db, req)
    items = section["items"]
    if not items:
        return _item("degisiklik_gecmisi", "Değişiklik Geçmişi", "eksik", "İzlenebilir bir mevzuat değişiklik geçmişi kaydı yok.")
    degisen = sum(1 for i in items if i["changed_since_assessment"])
    aciklama = (
        f"{len(items)} mevzuat değerlendirmesi izleniyor, hepsi güncel versiyonla uyumlu."
        if degisen == 0
        else f"{len(items)} mevzuat değerlendirmesi izleniyor, {degisen} tanesi güncel versiyondan farklı değerlendirilmiş."
    )
    return _item("degisiklik_gecmisi", "Değişiklik Geçmişi", "tamam", aciklama)


def build_compliance_dossier(db: Session, sku_id: str) -> dict | None:
    sku = db.get(ProductSku, sku_id)
    if sku is None:
        return None

    recipe = db.get(Recipe, sku.current_recipe_id) if sku.current_recipe_id else None
    req = recipe.packaging_request if recipe is not None else None
    materials = [layer.material for layer in recipe.layers if layer.material is not None] if recipe is not None else []

    items = [
        _urun_tanimi_item(sku),
        _recete_item(recipe),
        _hammadde_item(materials),
        _tedarikci_belgeleri_item(materials),
        _ppwr_kontrolleri_item(db, req),
        _gida_temas_item(db, req),
        _testler_item(db, recipe),
        _karbon_hesabi_item(materials),
        _uretim_kayitlari_item(db, recipe),
        _mevzuat_surumleri_item(db, req),
        _degisiklik_gecmisi_item(db, req),
    ]
    return {"sku_id": sku.id, "sku_code": sku.sku_code, "items": items}
