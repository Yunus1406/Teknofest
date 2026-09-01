"""Aşama 2-5 orkestrasyonu: ambalaj tanımlama, mevzuat değerlendirmesi,
firma altyapısı eşleştirmesi ve akıllı başlangıç reçetesi."""
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.constraint_engine.types import EvaluationTier, EvaluationVerdict
from app.llm.spec_extraction import extract_fields_from_spec_text
from app.models.enums import PackagingStatus, RecipeSource, RegulatoryVerdict
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
from app.models.chemical_restriction import ChemicalRestriction
from app.models.knowledge import Material, Polymer, Regulation
from app.models.recyclability_criterion import RecyclabilityCriterion
from app.models.recipe import (
    PackagingRequest,
    Recipe,
    RecipeLayer,
    RegulatoryAssessment,
)
from app.models.regulation_requirement import RegulationRequirement
from app.optimization.candidate_generator import thickness_weights_for_layer_count
from app.services.common import canonical_packaging_category, preferred_polymer_codes


# --- Aşama 2: Ambalaj Tanımlama ------------------------------------------

def create_packaging_request(db: Session, data: dict) -> PackagingRequest:
    req = PackagingRequest(**data, status=PackagingStatus.DRAFT.value)
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def update_packaging_request(db: Session, req: PackagingRequest, data: dict) -> PackagingRequest:
    """Kullanıcı, şartname çıkarımından sonra formu düzenleyip kaydettiğinde
    (veya taslağı sonradan güncellediğinde) kullanılır."""
    for field in (
        "packaging_type",
        "usage_area",
        "product",
        "target_market",
        "food_contact",
        "target_volume_units",
        "dimensions",
        "target_thickness_micron",
        "target_gsm",
        "physical_performance_notes",
    ):
        if field in data:
            setattr(req, field, data[field])
    db.commit()
    db.refresh(req)
    return req


def extract_spec(db: Session, packaging_request: PackagingRequest, spec_text: str, file_name: str | None) -> dict:
    extracted = extract_fields_from_spec_text(spec_text)
    packaging_request.extracted_fields = extracted
    if file_name:
        packaging_request.spec_file_name = file_name
    db.commit()
    return extracted


# --- Aşama 3: Mevzuat ve Tasarım Kriterleri -------------------------------

def assess_regulations(db: Session, packaging_request: PackagingRequest) -> tuple[str, list[RegulatoryAssessment]]:
    category = canonical_packaging_category(packaging_request.packaging_type)
    regulations = db.execute(select(Regulation)).scalars().all()
    matched = [r for r in regulations if category in (r.applicable_packaging_types or [])]
    if not matched:
        matched = list(regulations)

    food_grade_pcr_exists = (
        db.query(Material)
        .filter(Material.material_type.in_(["pcr", "regranul"]), Material.food_contact_eligible.is_(True))
        .first()
        is not None
    )

    # PFAS (PPWR Md.5) ve GMP (EU 2023/2006) yalnızca gıda temaslı
    # ambalajlarda uygulanır — ambalaj TÜRÜNE (kategoriye) göre değil,
    # food_contact bayrağına göre dahil edilir/çıkarılır (kategori
    # eşleşmesi bunu garanti etmez, applicable_packaging_types BİLİNÇLİ BOŞ).
    for code in ("PPWR-ART-5", "EU-GMP-2023-2006"):
        reg = next((r for r in regulations if r.code == code), None)
        if reg is not None:
            matched = [r for r in matched if r.code != code]
            if packaging_request.food_contact:
                matched.append(reg)

    # Faz L.2 (Madde 4) — (EU) 2022/1616, gıda temaslı geri dönüştürülmüş
    # plastik (rPET/PCR) çerçevesi: (EU) 10/2011'in YERİNE değil, EK OLARAK,
    # SADECE gıda temaslı VE bilgi tabanında gıda sınıfı sertifikalı bir
    # PCR/regranül malzeme varsa devreye girer (aynı `food_grade_pcr_exists`
    # sinyali FCM'nin zaten kullandığı sorgu -- yeni bir DB taraması gerekmez).
    recycled_fcm_reg = next((r for r in regulations if r.code == "EU-2022-1616"), None)
    if recycled_fcm_reg is not None:
        matched = [r for r in matched if r.code != "EU-2022-1616"]
        if packaging_request.food_contact and food_grade_pcr_exists:
            matched.append(recycled_fcm_reg)

    # Var olan değerlendirmeleri temizle (aşama yeniden çalıştırılabilir)
    db.query(RegulatoryAssessment).filter_by(
        packaging_request_id=packaging_request.id
    ).delete()

    # Faz L.1 — Hedef Pazar karar düğümü. Bu mevzuatlar (PPWR/EU) AB
    # mevzuatıdır; hedef pazar AÇIKÇA AB-dışıysa bu SADECE bilgilendirme
    # amaçlı işaretlenir (reasoning'e not eklenir, decision_trail'e yazılır)
    # -- verdict/sayaçlar ASLA değişmez, hiçbir madde sessizce filtrelenmez
    # (yanlış negatif riski, yanlış pozitiften daha tehlikelidir).
    market_status = _target_market_eu_status(packaging_request.target_market)

    assessments: list[RegulatoryAssessment] = []
    for reg in matched:
        verdict, reasoning = _assess_single_regulation(db, reg, packaging_request, food_grade_pcr_exists)
        if market_status == "hayir":
            reasoning += (
                f" | Not: Hedef pazar '{packaging_request.target_market}' — bu mevzuat (AB) bu pazar "
                "için doğrudan yürürlükte olmayabilir, hedef pazarın kendi mevzuatı ayrıca kontrol edilmeli."
            )
        row = RegulatoryAssessment(
            packaging_request_id=packaging_request.id,
            regulation_id=reg.id,
            verdict=verdict,
            reasoning=reasoning,
            recyclability_breakdown=_recyclability_breakdown(db, reg),
            decision_trail=_build_decision_trail(db, reg, packaging_request, category, market_status),
            regulation_version_snapshot=_current_requirement_version(db, reg.id),
        )
        db.add(row)
        assessments.append(row)

    overall = _overall_verdict([a.verdict for a in assessments])
    packaging_request.status = PackagingStatus.ASSESSED.value
    db.commit()
    for a in assessments:
        db.refresh(a)
    return overall, assessments


def _target_market_eu_status(target_market: str | None) -> str:
    """Faz L.1 — "evet" (AB/Avrupa açıkça belirtilmiş), "hayir" (açıkça
    başka bir pazar belirtilmiş) veya "belirsiz" (boş/tanınmayan metin)
    döner. "belirsiz" durumunda mevcut davranış (mevzuat değerlendirilir)
    KORUNUR -- eksik/belirsiz veriden dolayı bir madde asla sessizce
    atlanmaz."""
    if not target_market:
        return "belirsiz"
    lowered = target_market.strip().lower()
    if re.search(r"avrupa|\bab\b|\beu\b", lowered):
        return "evet"
    if re.search(r"t[üu]rkiye|\babd\b|amerika|\busa\b|ingiltere|\buk\b|birle[şs]ik krall", lowered):
        return "hayir"
    return "belirsiz"


def _current_requirement_version(db: Session, regulation_id: str) -> str | None:
    """Faz L.3 (Madde 16) — bu regülasyonun İLK `RegulationRequirement`
    satırının GÜNCEL `version`'ını döner (yoksa None). `RegulatoryAssessment.
    regulation_version_snapshot`'a donmuş olarak yazılır -- mevzuat daha
    sonra güncellenirse bu snapshot DEĞİŞMEZ, L.4'ün etki analizinin
    dayandığı sinyal budur."""
    row = (
        db.query(RegulationRequirement)
        .filter_by(regulation_id=regulation_id)
        .order_by(RegulationRequirement.target_year)
        .first()
    )
    return row.version if row else None


def _build_decision_trail(
    db: Session, reg: Regulation, req: PackagingRequest, category: str, market_status: str
) -> dict:
    """Faz L.1 — "Bu kural neden uygulanıyor?" panelinin yapılandırılmış
    verisi: Hedef Pazar → Ambalaj Malzemesi (tahmini) → Kullanım → Gıda
    Teması → Ambalaj Kategorisi → İstisna → Uygulanacak Madde → Hedef
    Tarih. Her adım ZATEN hesaplanmış/DB'den okunan gerçek veriye dayanır,
    hiçbir adım uydurulmaz."""
    requirements = (
        db.query(RegulationRequirement)
        .filter_by(regulation_id=reg.id)
        .order_by(RegulationRequirement.target_year)
        .all()
    )
    row = requirements[0] if requirements else None
    preferred = preferred_polymer_codes(req.packaging_type)
    return {
        "hedef_pazar": req.target_market,
        "hedef_pazar_ab_mi": market_status,
        "ambalaj_malzemesi_tahmini": (
            f"'{req.packaging_type}' ifadesinden tahmini tercih sırası: {'/'.join(preferred)} "
            "(reçete henüz üretilmediği için TAHMİNİ)"
        ),
        # Faz N.1b (Madde 14) — bu alan HER ZAMAN "dusuk": reçete/malzeme
        # Aşama 3'te henüz seçilmedi, bu yüzden hangi polimer kullanılacağı
        # bir TAHMİNDİR (packaging_type serbest metninden çıkarılır). Bu
        # dürüst bir sabit -- "hangi anahtar kelime eşleşti" gibi bir
        # nüansla "orta" gibi uydurma bir ara güven seviyesi ÜRETİLMEZ.
        "ambalaj_malzemesi_guveni": "dusuk",
        "kullanim_alani": req.usage_area,
        "gida_temasi": req.food_contact,
        "ambalaj_kategorisi": category,
        "istisna": row.exception_text if row else None,
        "uygulanan_madde": _article_citation(row, reg.code),
        "hedef_tarih": row.target_year if row else None,
    }


def _overall_verdict(verdicts: list[str]) -> str:
    """Faz G.2 — 5 durumlu "en kötü kazanır" sıralaması: kesin bir uygunsuzluk
    (`NOT_OK`) veya insan kararı gerektiren bir durum (`REVIEW`) her zaman en
    önde; `MISSING_DATA`/`NO_METHODOLOGY` bir onay/red İDDİASI DEĞİLDİR (sadece
    "bunu otomatik olarak değerlendiremedik" bilgisidir), bu yüzden ikisi de
    `OK`'den önce ama `NOT_OK`/`REVIEW`'den sonra gelir."""
    priority = [
        RegulatoryVerdict.NOT_OK.value,
        RegulatoryVerdict.REVIEW.value,
        RegulatoryVerdict.MISSING_DATA.value,
        RegulatoryVerdict.NO_METHODOLOGY.value,
    ]
    for v in priority:
        if v in verdicts:
            return v
    return RegulatoryVerdict.OK.value


def _recyclability_breakdown(db: Session, reg: Regulation) -> dict | None:
    """Faz F.9 — SADECE PPWR Md.6 (PPWR-ART-6, geri dönüştürülebilirlik)
    değerlendirmesi için doldurulur; diğer TÜM maddelerde None kalır. Md.6'nın
    kendi verdict/reasoning hesaplaması (generic yol, RegulationRequirement
    satırından, bkz. _assess_single_regulation) BU FONKSİYONLA HİÇ
    ETKİLEŞMEZ -- bu tamamen ayrı, opsiyonel bir zenginleştirme katmanıdır."""
    if reg.code != "PPWR-ART-6":
        return None
    criteria = db.query(RecyclabilityCriterion).all()
    if not criteria:
        return None
    return {
        "dimensions": [
            {
                "dimension": c.dimension,
                "criterion_text": c.criterion_text,
                "weight_pct": c.weight_pct,
                "packaging_category": c.packaging_category,
            }
            for c in criteria
        ]
    }


def _assess_single_regulation(
    db: Session, reg: Regulation, req: PackagingRequest, food_grade_pcr_exists: bool
) -> tuple[str, str]:
    """Faz B.8 — madde numarası/gereklilik metni artık burada Python
    if/elif dallarında HARDCODE değil, `RegulationRequirement` tablosundan
    okunur (bkz. app/models/regulation_requirement.py). Yalnızca GERÇEKTEN
    çalışma zamanı verisine bağlı üç madde (minimizasyon: boyut girildi mi;
    PCR içerik: kategori+yıl tablosundan seçim; FCM: iki seviyeli
    değerlendirme) kendi küçük prosedürel fonksiyonuna yönlendirilir — bunlar
    dışındaki HER madde (bugünkü ART-6/ART-9/ART-5 ve yarın eklenecek her
    yeni madde) hiçbir kod değişikliği gerektirmeden DOĞRUDAN DB satırından
    karar+metin okuyan genel yolu kullanır."""
    requirements = (
        db.query(RegulationRequirement)
        .filter_by(regulation_id=reg.id)
        .order_by(RegulationRequirement.target_year)
        .all()
    )

    if reg.code == "PPWR-ART-10":
        return _assess_minimization(requirements, req)
    if reg.code == "PPWR-ART-7":
        return _assess_pcr_content(requirements, req, food_grade_pcr_exists)
    if reg.code == "EU-FCM-1935-2004":
        return _assess_fcm(requirements, req, food_grade_pcr_exists)
    if reg.code == "PPWR-ART-5":
        return _assess_pfas(db, reg, requirements)

    # Genel yol: tek satırlık maddeler DOĞRUDAN DB'deki karar+metni döner.
    if requirements:
        row = requirements[0]
        return (row.default_verdict, row.requirement_text)
    # Faz G.2 — bu bir "inceleme gerektiren belirsiz durum" değil, sistemin
    # bu madde için hiç RegulationRequirement satırı olmadığı GERÇEĞİDİR.
    return (
        RegulatoryVerdict.MISSING_DATA.value,
        "Bu madde için bilgi tabanında henüz bir gereklilik satırı tanımlı değil.",
    )


def _article_citation(row: "RegulationRequirement | None", fallback: str) -> str:
    """Faz G.2 — `article` ("Md.10") ile `sub_article` ("Ek IV"/"Fıkra 5")
    ayrı alanlar; reasoning metinlerinde ikisini birlikte gösterir."""
    if row is None:
        return fallback
    return f"{row.article} ({row.sub_article})" if row.sub_article else row.article


def _assess_minimization(
    requirements: list[RegulationRequirement], req: PackagingRequest
) -> tuple[str, str]:
    article = _article_citation(requirements[0] if requirements else None, "Md.10")
    if not req.dimensions:
        return (
            RegulatoryVerdict.MISSING_DATA.value,
            f"Ambalaj minimizasyonu (PPWR {article}) için ölçü/hacim verisi eksik; "
            "boyutlar girildiğinde otomatik değerlendirilecek.",
        )
    return (
        RegulatoryVerdict.OK.value,
        f"Hedef ölçüler girildi; kesin minimizasyon uygunluğu (PPWR {article} "
        "performans kriterleri) reçete (Aşama 6) üretildiğinde katman kalınlığı "
        "üzerinden doğrulanacak.",
    )


def _assess_fcm(
    requirements: list[RegulationRequirement], req: PackagingRequest, food_grade_pcr_exists: bool
) -> tuple[str, str]:
    if not req.food_contact:
        return (
            RegulatoryVerdict.OK.value,
            "Ambalaj gıda ile doğrudan temas etmiyor; bu tüzük kapsam dışı.",
        )
    # İki seviyeli değerlendirme: bilgi tabanındaki bir hammaddenin
    # sertifikalı olması, NİHAİ ambalajın (migrasyon testi vb.) uygun
    # olduğu anlamına gelmez — bu ikisi asla tek bir 'Uygun' ile
    # birleştirilmemeli.
    regulation_no = requirements[0].regulation_no if requirements else "EU 1935/2004"
    raw_material_status = (
        "Hammadde Belgesi Mevcut ✓ (bilgi tabanında gıda sınıfı sertifikalı hammadde var)"
        if food_grade_pcr_exists
        else "Hammadde Belgesi: Doğrulama Gerekli (bilgi tabanında gıda sınıfı "
        "sertifikalı hammadde henüz onaylanmadı)"
    )
    # Faz G.2 — bu "belirsiz bir vaka, insan karar versin" durumu DEĞİL: nihai
    # ambalajın migrasyon/uygunluk testlerinden geçtiğini doğrulamak yapısal
    # olarak otomatikleştirilemez (gerçek bir laboratuvar testi gerekir),
    # hammadde sertifikalı olsun olmasın bu değişmez — bu yüzden her zaman
    # NO_METHODOLOGY, REVIEW değil.
    return (
        RegulatoryVerdict.NO_METHODOLOGY.value,
        f"{raw_material_status} | Nihai Ambalaj Uygunluğu: Doğrulama Gerekli — tek bir "
        "hammaddenin sertifikalı olması, nihai ürünün migrasyon/uygunluk testlerinden "
        f"geçtiği anlamına gelmez ({regulation_no}). Bu doğrulama otomatikleştirilemez, "
        "laboratuvar testi gerekir.",
    )


def build_food_contact_evidence_checklist(db: Session, req: PackagingRequest) -> list[dict]:
    """Faz L.2 (Madde 4) — gıda temaslı ambalajlar için otomatik kanıt
    yönetim listesi: 1935/2004, (EU) 10/2011, GMP 2023/2006, (varsa) (EU)
    2022/1616, DoC, Genel/Spesifik Migrasyon, Hammadde Uygunluk Belgeleri,
    PCR/rPET Kaynak-Proses Kanıtları, Kimyasal/Test Kanıtları. Reçete henüz
    üretilmediği (Aşama 5-6'dan önce) için hammadde-bazlı kanıtlar KB
    GENELİNDE bir sinyal olup olmadığına bakar (`food_grade_pcr_exists` ile
    AYNI disiplin) -- hiçbir kanıt, gerçek bir veri sinyali olmadan "mevcut"
    işaretlenmez; belge-yükleme gerektiren kanıtlar (DoC, GMP denetimi,
    migrasyon/PFAS testi) bu sistemde hiç izlenmediğinden dürüstçe "eksik"
    kalır."""
    if not req.food_contact:
        return []

    certified_material_exists = (
        db.query(Material).filter(Material.certification_status.isnot(None)).first() is not None
    )
    pcr_source_documented = (
        db.query(Material)
        .filter(Material.material_type.in_(["pcr", "regranul"]), Material.source.isnot(None))
        .first()
        is not None
    )
    food_grade_pcr_exists = (
        db.query(Material)
        .filter(Material.material_type.in_(["pcr", "regranul"]), Material.food_contact_eligible.is_(True))
        .first()
        is not None
    )

    def _item(evidence_type: str, regulation_ref: str | None, status: str, notes: str) -> dict:
        return {"evidence_type": evidence_type, "regulation_ref": regulation_ref, "status": status, "notes": notes}

    return [
        _item(
            "1935/2004 Çerçeve Uygunluğu (DoC)", "EU 1935/2004", "eksik",
            "Uygunluk Beyanı (DoC) belgesi bu sistemde yüklenmedi; tedarikçiden temin edilmeli.",
        ),
        _item(
            "(EU) 10/2011 Migrasyon Limitleri", "EU 10/2011", "eksik",
            "Genel/spesifik migrasyon test sonucu bu sistemde kayıtlı değil; laboratuvar testi gerekir.",
        ),
        _item(
            "GMP 2023/2006 İyi Üretim Uygulamaları", "EC 2023/2006", "eksik",
            "Üretici GMP denetim/sertifika kaydı bu sistemde izlenmiyor.",
        ),
        _item(
            "(EU) 2022/1616 Geri Dönüştürülmüş Plastik Çerçevesi", "EU 2022/1616",
            "eksik" if food_grade_pcr_exists else "gerekli_degil",
            (
                "Gıda temaslı geri dönüşüm teknolojisi yetkilendirme belgesi gerekir "
                "((EU) 10/2011'e ek olarak)."
                if food_grade_pcr_exists
                else "Bilgi tabanında gıda sınıfı sertifikalı PCR/regranül malzeme yok; "
                "bu çerçeve şu an tetiklenmiyor."
            ),
        ),
        _item(
            "DoC (Uygunluk Beyanı)", None, "eksik",
            "Genel uygunluk beyanı belgesi bu sistemde yüklenmedi.",
        ),
        _item(
            "Genel/Spesifik Migrasyon Testi", "EU 10/2011", "eksik",
            "Migrasyon test raporu bu sistemde kayıtlı değil.",
        ),
        _item(
            "Hammadde Uygunluk Belgeleri", None,
            "mevcut" if certified_material_exists else "eksik",
            (
                "Bilgi tabanında sertifikasyon durumu girilmiş en az bir hammadde var."
                if certified_material_exists
                else "Bilgi tabanında sertifikasyon durumu girilmiş hiçbir hammadde henüz yok."
            ),
        ),
        _item(
            "PCR/rPET Kaynak ve Proses Kanıtları", None,
            "mevcut" if pcr_source_documented else "eksik",
            (
                "Bilgi tabanında kaynağı belgelenmiş en az bir PCR/regranül malzeme var."
                if pcr_source_documented
                else "Bilgi tabanında kaynağı belgelenmiş bir PCR/regranül malzeme henüz yok."
            ),
        ),
        _item(
            "Kimyasal/Test Kanıtları (PFAS vb.)", "PPWR Md.5(5)", "eksik",
            "PFAS içerik testi bu sistemde kayıtlı değil; laboratuvar testi gerekir.",
        ),
    ]


_VERDICT_LABELS: dict[str, str] = {
    RegulatoryVerdict.OK.value: "Uygun Görünüyor",
    RegulatoryVerdict.REVIEW.value: "İnceleme Gerekli",
    RegulatoryVerdict.NOT_OK.value: "Uygun Değil",
    RegulatoryVerdict.MISSING_DATA.value: "Veri Eksik",
    RegulatoryVerdict.NO_METHODOLOGY.value: "Henüz Uygulanabilir Metodoloji Bulunmuyor",
}


def _assess_pfas(
    db: Session, reg: Regulation, requirements: list[RegulationRequirement]
) -> tuple[str, str]:
    """PFAS (PPWR Md.5(5)) limitleri artık `ChemicalRestriction` tablosundan
    okunur (Faz F.4) -- eskiden bu sayılar SADECE requirement_text
    prozasında gömülüydü, hiçbir kod okumuyordu.

    Faz G.2 — verdict mantığı iki ayrı duruma ayrıldı: referans limit verisi
    (`ChemicalRestriction`) HİÇ yüklenmemişse bu "veri eksik"tir
    (`MISSING_DATA`); veri yüklenmiş olsa BİLE, gerçek ppb/ppm içeriğinin
    ambalajda ölçülmesi bir laboratuvar testi gerektirir -- bu yapısal olarak
    otomatikleştirilemez (`NO_METHODOLOGY`), "kullanıcı karar versin"
    (`REVIEW`) durumu DEĞİLDİR."""
    article = _article_citation(requirements[0] if requirements else None, "Md.5(5)")

    restrictions = db.query(ChemicalRestriction).filter_by(regulation_id=reg.id, substance_group="PFAS").all()
    if not restrictions:
        # Referans veri hiç yüklenmemişse (ör. eski bir DB) -- bu bir veri
        # eksikliğidir, sessizce uydurma bir sayı gösterilmez.
        text = requirements[0].requirement_text if requirements else "PFAS limitleri tanımlı değil."
        return RegulatoryVerdict.MISSING_DATA.value, text

    by_type = {r.restriction_type: r for r in restrictions}
    parts = []
    if single := by_type.get("tekil_madde_siniri"):
        parts.append(f"tekil PFAS ≤{single.limit_value:g} {single.limit_unit}")
    if total_target := by_type.get("toplam_hedef"):
        parts.append(f"toplam PFAS ≤{total_target.limit_value:g} {total_target.limit_unit} hedef")
    if total_limit := by_type.get("toplam_sinir"):
        parts.append(f"toplam PFAS ≤{total_limit.limit_value:g} {total_limit.limit_unit} sınır")

    verdict = RegulatoryVerdict.NO_METHODOLOGY.value
    reasoning = (
        f"PFAS Kontrolü — PPWR {article} | "
        f"Gıda temaslı ambalaj olduğu için uygulanır ({', '.join(parts)}) | "
        "Kanıt durumu: Belge/Test Verisi Gerekli — gerçek PFAS içeriği ancak "
        "laboratuvar testiyle doğrulanabilir, otomatik değerlendirilemez | "
        f"Sonuç: {_VERDICT_LABELS.get(verdict, verdict)}"
    )
    return verdict, reasoning


_PCR_CATEGORY_DISPLAY_NAMES: dict[str, str] = {
    "gida_temasli_pet_disi_plastik": "Gıda temaslı / PET dışı plastik",
}


def _pcr_category_key(food_contact: bool, is_pet: bool) -> str:
    fc = "gida_temasli" if food_contact else "gida_temasli_degil"
    pet = "pet" if is_pet else "pet_disi"
    return f"{fc}_{pet}_plastik"


def _assess_pcr_content(
    requirements: list[RegulationRequirement], req: PackagingRequest, food_grade_pcr_exists: bool
) -> tuple[str, str]:
    """PPWR Md.7 — sabit bir yüzde yerine `RegulationRequirement` tablosundaki
    kategori+yıl satırlarından okunur (bkz. regulation_requirements.yaml).
    Reçete henüz üretilmediği için (Aşama 5-6'dan önce) PET olup olmadığı
    yalnızca ambalaj türünden TAHMİNİ olarak çıkarılır; bu tahminî doğası
    reasoning metninde belirtilir."""
    is_pet_guess = preferred_polymer_codes(req.packaging_type)[0] == "PET"
    category_key = _pcr_category_key(req.food_contact, is_pet_guess)
    rows = sorted(
        (r for r in requirements if r.packaging_category == category_key),
        key=lambda r: r.target_year or 0,
    )

    if not rows:
        return (
            RegulatoryVerdict.MISSING_DATA.value,
            "Geri Dönüştürülmüş İçerik — PPWR Md.7 | Bu ambalaj kategorisi için "
            "(gıda teması + polimer türü kombinasyonu) bilgi tabanında doğrulanmış bir "
            "hedef yüzde henüz tanımlı değil; sabit bir oran varsayılmadı. Kategori "
            "tabloya eklendiğinde otomatik değerlendirilecek.",
        )

    category_name = _PCR_CATEGORY_DISPLAY_NAMES.get(category_key, category_key)
    requirement_lines = " | ".join(r.requirement_text for r in rows)
    exception = rows[0].exception_text or "İstisna, tarih ve metodoloji ayrıca doğrulanmalı."
    reasoning = (
        "Geri Dönüştürülmüş İçerik — PPWR Md.7 | "
        f"Kategori: {category_name} (tahmini, ambalaj türünden çıkarıldı) | "
        f"{requirement_lines} | "
        "Regranül/PIR: Md.7 hesabına dahil değil | "
        f"*{exception}"
    )

    if req.food_contact and not food_grade_pcr_exists:
        reasoning += (
            " | Ek not: gıda temaslı ambalajlarda PCR ancak gıda sınıfı sertifikalı "
            "hammadde ile kullanılabilir; bilgi tabanında uygun sertifikalı hammadde "
            "henüz doğrulanmadı."
        )
        # Faz G.2 — bu bir belirsizlik/karar bekleyen durum değil, bilgi
        # tabanında eksik bir veri (sertifikalı hammadde kaydı) durumudur.
        return RegulatoryVerdict.MISSING_DATA.value, reasoning

    return RegulatoryVerdict.OK.value, reasoning


# --- Aşama 4: Firma Altyapısı ve Otomatik Eşleştirme ----------------------

# Faz K.4 (Madde 6) — her kriterin skora katkısı. Toplamı 1.0'dır. Bu skor
# SADECE bilgilendirme/gerekçelendirme amaçlıdır -- bağlayıcı kısıtlar
# constraint_engine'de (Faz K.6/K.7) ayrıca uygulanır.
_MATCH_CRITERIA_WEIGHTS: dict[str, float] = {
    "ambalaj_turu": 0.30,
    "malzeme_uyumu": 0.30,
    "mikron_araligi": 0.20,
    "proses": 0.10,
    "katman_yapisi": 0.10,
}


def match_infrastructure(db: Session, packaging_request: PackagingRequest) -> list[dict]:
    """Faz K.4 (Madde 6) — önceden sadece ambalaj türü desteği kontrol
    edilir, uymayan hatlar hiçbir gerekçe tutulmadan SESSİZCE elenirdi ("uygun
    üretim hattı bulunamadı" derken hiçbir açıklama yoktu). Artık TÜM aktif
    hatlar için 5 kriter (proses/aktiflik, malzeme-polimer uyumu, mikron
    aralığı, katman yapısı, ambalaj türü desteği) ayrı ayrı değerlendirilir;
    uygun OLMAYAN hatlar da sonuçta kalır (`eligible=False`, `missing` dolu),
    kullanıcı NEDEN elendiğini görebilir. Sonuç önce uygunluğa (eligible),
    sonra skora göre sıralanır -- ki `matches[0]` her zaman (varsa) uygun bir
    hat olsun; bu, seed_demo.py ve Aşama 4'ün "ilk eşleşeni öner" mantığının
    yanlışlıkla uygunsuz bir hat seçmesini engeller."""
    category = canonical_packaging_category(packaging_request.packaging_type)
    preferred_codes = preferred_polymer_codes(packaging_request.packaging_type)
    target_thickness = packaging_request.target_thickness_micron

    lines = (
        db.execute(
            select(ProductionLine).options(selectinload(ProductionLine.material_compatibility))
        )
        .scalars()
        .all()
    )
    # LineMaterialCompatibility bir `material` ilişkisi TAŞIMAZ (sadece
    # material_id FK) -- malzeme+polimer bilgisini tek sorguda toplu çekip
    # id'ye göre sözlükte tutuyoruz.
    all_material_ids = {c.material_id for line in lines for c in line.material_compatibility}
    materials_by_id: dict[str, Material] = {}
    if all_material_ids:
        materials_by_id = {
            m.id: m
            for m in db.execute(
                select(Material).options(selectinload(Material.polymer)).filter(Material.id.in_(all_material_ids))
            ).scalars()
        }

    results: list[dict] = []
    for line in lines:
        if not line.active:
            continue  # pasif hatlar hiç gösterilmez (önceki davranışla aynı)

        supported_categories = {
            canonical_packaging_category(t) for t in (line.supported_packaging_types or [])
        }
        ambalaj_turu_ok = category in supported_categories

        compatible_ids = [c.material_id for c in line.material_compatibility]
        malzeme_uyumu_ok = False
        for c in line.material_compatibility:
            material = materials_by_id.get(c.material_id)
            if material is None or material.polymer is None:
                continue
            if material.polymer.code not in preferred_codes:
                continue
            if packaging_request.food_contact and not material.food_contact_eligible:
                continue
            malzeme_uyumu_ok = True
            break

        # Hedef kalınlık hiç girilmemişse (None) bu kriter değerlendirilemez
        # -- eksik veriden dolayı bir hattı ENGELLEMEK yanlış olur.
        mikron_araligi_ok = (
            True if target_thickness is None else line.min_micron <= target_thickness <= line.max_micron
        )
        proses_ok = bool(line.process_type)
        katman_yapisi_ok = bool(line.layer_structure) and line.layer_count >= 1

        criteria = {
            "proses": proses_ok,
            "malzeme_uyumu": malzeme_uyumu_ok,
            "mikron_araligi": mikron_araligi_ok,
            "katman_yapisi": katman_yapisi_ok,
            "ambalaj_turu": ambalaj_turu_ok,
        }
        score_pct = round(sum(_MATCH_CRITERIA_WEIGHTS[k] for k, ok in criteria.items() if ok) * 100)
        eligible = ambalaj_turu_ok and malzeme_uyumu_ok and mikron_araligi_ok

        missing: list[str] = []
        if not ambalaj_turu_ok:
            missing.append(f"'{packaging_request.packaging_type}' ambalaj türü desteklenmiyor")
        if not malzeme_uyumu_ok:
            missing.append(f"{'/'.join(preferred_codes)} uyumlu hammadde tanımı")
        if not mikron_araligi_ok:
            missing.append(
                f"{target_thickness:.0f} µm hedefi hattın {line.min_micron:.0f}-{line.max_micron:.0f} µm "
                "aralığı dışında"
            )
        if not proses_ok:
            missing.append("proses tipi tanımlı değil")
        if not katman_yapisi_ok:
            missing.append("katman yapısı tanımlı değil")

        reason = (
            (
                f"'{packaging_request.packaging_type}' türü destekleniyor; "
                f"katman yapısı {line.layer_structure}, mikron aralığı "
                f"{line.min_micron:.0f}-{line.max_micron:.0f}, {len(compatible_ids)} uyumlu "
                "hammadde eşleşti."
            )
            if eligible
            else ("Eksik: " + "; ".join(missing))
        )

        results.append(
            {
                "line": line,
                "compatible_material_ids": compatible_ids,
                "match_reason": reason,
                "eligible": eligible,
                "score_pct": score_pct,
                "criteria": criteria,
                "missing": missing,
                # Faz N.1b (Madde 14) — `mikron_araligi` kriteri hedef kalınlık
                # hiç girilmemişse GERÇEKTEN değerlendirilmiyor, sessizce
                # "geçti" VARSAYILIYOR (bkz. yukarıdaki mikron_araligi_ok
                # hesaplaması). Bu, score_pct'in bir kısmının varsayıma
                # dayandığını AÇIKÇA işaretler -- önceden hiç belirtilmiyordu.
                "mikron_araligi_veri_guveni": "varsayimsal" if target_thickness is None else "yuksek",
            }
        )

    results.sort(key=lambda r: (r["eligible"], r["score_pct"]), reverse=True)

    if any(r["eligible"] for r in results):
        packaging_request.status = PackagingStatus.MATCHED.value
        db.commit()
    return results


# --- Aşama 5: Mevcut Reçete / Akıllı Başlangıç ----------------------------

@dataclass
class ReferenceSearchResult:
    """Faz G.4 — firma hafızası taramasının GERÇEK sonucu: hangi kademede
    kaç doğrulanmış aday bulunduğu. `recipe` None ise hiçbir kademe eşleşme
    üretmedi -- Aşama 5 bu durumda kural tabanlı (virgin-only) bir başlangıç
    reçetesi üretir (mevcut davranış, bkz. generate_initial_recipe)."""

    recipe: Recipe | None
    tier: str | None = None
    evidence_count: int = 0
    candidate_recipe_ids: list[str] = field(default_factory=list)


_TOLERANCE_PCT = 0.20  # G.4: "benzer teknik şartlar" için ±%20 tolerans


def _within_tolerance(target: float | None, candidate: float | None, pct: float = _TOLERANCE_PCT) -> bool:
    if target is None or candidate is None:
        return False
    return abs(candidate - target) <= pct * target


def find_reference_recipe_with_evidence(
    db: Session, packaging_request: PackagingRequest, line_id: str | None = None
) -> ReferenceSearchResult:
    """Faz G.4 — 5 kademeli firma hafızası taraması, HER kademe SADECE bir
    öncekinde hiç eşleşme yoksa denenir (kademe 1 en kesin/güvenilir kanıt,
    kademe 5 en gevşek):
      1. aynı SKU'nun doğrulanmış GEÇERLİ (current_recipe_id) reçetesi
      2. aynı ambalaj türü metni (Faz B.5'in eski tek kademeli davranışı)
      3. benzer kullanım alanı (usage_area eşleşmesi, ambalaj türünden
         bağımsız)
      4. benzer teknik şartlar (Faz G.1'in target_thickness_micron/
         target_gsm alanlarına ±%20 tolerans)
      5. aynı üretim hattında üretilmiş diğer doğrulanmış reçeteler
    Her kademede eşleşen TÜM doğrulanmış adaylar sayılır (`evidence_count`)
    -- sadece ilkini almak "kaç tanesi doğruladı" sorusuna cevap vermez."""
    # Kademe 1: aynı SKU'nun kendi geçerli reçetesi.
    if packaging_request.sku_id and packaging_request.sku and packaging_request.sku.current_recipe_id:
        sku_recipe = db.get(Recipe, packaging_request.sku.current_recipe_id)
        if sku_recipe is not None and sku_recipe.is_verified:
            return ReferenceSearchResult(
                recipe=sku_recipe, tier="ayni_sku", evidence_count=1, candidate_recipe_ids=[sku_recipe.id]
            )

    base_query = db.query(Recipe).join(PackagingRequest).filter(
        Recipe.is_verified.is_(True),
        Recipe.packaging_request_id != packaging_request.id,
    )

    # Kademe 2: aynı ambalaj türü metni.
    same_type = (
        base_query.filter(PackagingRequest.packaging_type == packaging_request.packaging_type)
        .order_by(Recipe.version.desc())
        .all()
    )
    if same_type:
        return ReferenceSearchResult(
            recipe=same_type[0], tier="ayni_ambalaj_turu",
            evidence_count=len(same_type), candidate_recipe_ids=[r.id for r in same_type],
        )

    # Kademe 3: benzer kullanım alanı (ambalaj türünden bağımsız).
    similar_usage = (
        base_query.filter(PackagingRequest.usage_area == packaging_request.usage_area)
        .order_by(Recipe.version.desc())
        .all()
    )
    if similar_usage:
        return ReferenceSearchResult(
            recipe=similar_usage[0], tier="benzer_kullanim_alani",
            evidence_count=len(similar_usage), candidate_recipe_ids=[r.id for r in similar_usage],
        )

    # Kademe 4: benzer teknik şartlar (Faz G.1'in yeni alanları) -- SADECE
    # mevcut talepte bu alanlardan en az biri girilmişse denenir; hiçbiri
    # girilmemişse "benzerlik" iddiası ANLAMSIZ olurdu.
    if packaging_request.target_thickness_micron is not None or packaging_request.target_gsm is not None:
        spec_candidates = base_query.all()
        similar_specs = []
        for r in spec_candidates:
            other = r.packaging_request
            checks = []
            if packaging_request.target_thickness_micron is not None:
                checks.append(_within_tolerance(packaging_request.target_thickness_micron, other.target_thickness_micron))
            if packaging_request.target_gsm is not None:
                checks.append(_within_tolerance(packaging_request.target_gsm, other.target_gsm))
            if checks and all(checks):
                similar_specs.append(r)
        if similar_specs:
            similar_specs.sort(key=lambda r: r.version, reverse=True)
            return ReferenceSearchResult(
                recipe=similar_specs[0], tier="benzer_teknik_sartlar",
                evidence_count=len(similar_specs), candidate_recipe_ids=[r.id for r in similar_specs],
            )

    # Kademe 5: aynı üretim hattında üretilmiş diğer doğrulanmış reçeteler.
    if line_id:
        same_line = (
            db.query(Recipe)
            .filter(
                Recipe.line_id == line_id, Recipe.is_verified.is_(True),
                Recipe.packaging_request_id != packaging_request.id,
            )
            .order_by(Recipe.version.desc())
            .all()
        )
        if same_line:
            return ReferenceSearchResult(
                recipe=same_line[0], tier="ayni_hat",
                evidence_count=len(same_line), candidate_recipe_ids=[r.id for r in same_line],
            )

    return ReferenceSearchResult(recipe=None)


def find_reference_recipe(db: Session, packaging_request: PackagingRequest) -> Recipe | None:
    """Faz B.5 (Faz G.4'te 5 kademeli bir kaskadın üstüne kuruldu) — geriye
    dönük uyumluluk için sadece eşleşen reçeteyi döner. Tam kanıt (hangi
    kademe, kaç aday) için `find_reference_recipe_with_evidence` kullanın
    (bkz. generate_initial_recipe)."""
    return find_reference_recipe_with_evidence(db, packaging_request).recipe


def generate_initial_recipe(db: Session, packaging_request: PackagingRequest, line: ProductionLine) -> Recipe:
    search = find_reference_recipe_with_evidence(db, packaging_request, line_id=line.id)
    reference = search.recipe

    if reference is not None:
        recipe = Recipe(
            packaging_request_id=packaging_request.id,
            version=1,
            line_id=line.id,
            source=RecipeSource.REFERANS.value,
            status="taslak",
            reference_search_evidence={
                "tier": search.tier,
                "evidence_count": search.evidence_count,
                "candidate_recipe_ids": search.candidate_recipe_ids,
            },
        )
        db.add(recipe)
        db.flush()
        for src_layer in reference.layers:
            db.add(
                RecipeLayer(
                    recipe_id=recipe.id,
                    layer_index=src_layer.layer_index,
                    layer_label=src_layer.layer_label,
                    material_id=src_layer.material_id,
                    ratio_pct=src_layer.ratio_pct,
                    thickness_micron=src_layer.thickness_micron,
                )
            )
        db.commit()
        db.refresh(recipe)
        return recipe

    # Geçmiş doğrulanmış reçete yok -> hammadde + hat + mevzuat sınırlarına
    # göre güvenli, tamamen virgin bir başlangıç reçetesi üret.
    layer_labels = line.layer_structure.split("/")
    preferred = preferred_polymer_codes(packaging_request.packaging_type)
    weights = thickness_weights_for_layer_count(line.layer_count)
    # Faz K.2 — Aşama 2'de girilen hedef kalınlık VARSA o kullanılır; hattın
    # min/max aralığının ortası SADECE hedef hiç girilmemişse (None) bir
    # yedek değerdir. Önceden bu satır hedefi hiç okumuyordu (ör. 450 µm
    # istenirken hattın 20-120 µm aralığının ortası olan 70 µm üretiliyordu).
    target_total_micron = packaging_request.target_thickness_micron or (
        (line.min_micron + line.max_micron) / 2
    )

    # Faz K.6 (Madde 8) — Ambalaj → Proses → Hat → Polimer → Hammadde
    # uyumluluk zinciri: SADECE bu ambalaj türü için tercih edilen polimer
    # kod(lar)ı + (varsa) hattın uyumlu malzeme listesi + gıda teması
    # kesişiminden bir virgin malzeme seçilir. Önceden bu arama boş dönerse
    # (hiçbir tercih edilen polimer bulunamazsa) sistem SESSİZCE veritabanının
    # İLK virgin malzemesine düşüyordu -- polimer/proses uyumu HİÇ kontrol
    # edilmeden (ör. PET/rPET termoform tepsisi için "PP Virgin Enjeksiyon
    # Sınıfı" seçilebiliyordu). Artık kesişim boşsa AÇIK bir hata döner.
    compatible_material_ids = {c.material_id for c in line.material_compatibility}
    virgin_material = None
    for code in preferred:
        query = db.query(Material).join(Polymer).filter(
            Polymer.code == code, Material.material_type == "virgin"
        )
        if compatible_material_ids:
            query = query.filter(Material.id.in_(compatible_material_ids))
        candidate = query.first()
        if candidate and (not packaging_request.food_contact or candidate.food_contact_eligible):
            virgin_material = candidate
            break
    if virgin_material is None:
        raise ValueError(
            f"'{packaging_request.packaging_type}' ambalaj türü için tercih edilen polimerlerle "
            f"({'/'.join(preferred)}) uyumlu bir virgin hammadde, '{line.name}' hattında/bilgi "
            "tabanında bulunamadı. Bu hat için uyumlu hammadde tanımlanmalı ya da başka bir hat seçilmeli."
        )

    # Faz K.7 (Madde 9) — persist etmeden önce katman kalınlıkları toplamının
    # gerçekten hedefe eşit olduğu doğrulanır. Bu dal tek malzeme/%100 oranlı
    # olduğu için normalde otomatik sağlanır (weights toplamı 1.0), ama bu
    # mantık ileride genişletilirse (ör. blend eklenirse) sessizce bozulmasın
    # diye burada da kilitlenir.
    layer_thickness_sum = sum(target_total_micron * w for w in weights)
    if abs(layer_thickness_sum - target_total_micron) > 0.5:
        raise ValueError(
            f"Katman kalınlıkları toplamı {layer_thickness_sum:.1f} µm, hedef "
            f"{target_total_micron:.1f} µm ile eşleşmiyor -- reçete üretilemedi."
        )

    recipe = Recipe(
        packaging_request_id=packaging_request.id,
        version=1,
        line_id=line.id,
        source=RecipeSource.URETILDI.value,
        status="taslak",
        total_micron=target_total_micron,
    )
    db.add(recipe)
    db.flush()
    for idx, (label, weight) in enumerate(zip(layer_labels, weights)):
        db.add(
            RecipeLayer(
                recipe_id=recipe.id,
                layer_index=idx,
                layer_label=label,
                material_id=virgin_material.id,
                ratio_pct=100.0,
                thickness_micron=target_total_micron * weight,
            )
        )
    db.commit()
    db.refresh(recipe)
    return recipe
