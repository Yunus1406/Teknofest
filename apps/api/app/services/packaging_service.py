"""Aşama 2-5 orkestrasyonu: ambalaj tanımlama, mevzuat değerlendirmesi,
firma altyapısı eşleştirmesi ve akıllı başlangıç reçetesi."""
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

    # PFAS (PPWR Md.5) yalnızca gıda temaslı ambalajlarda uygulanır —
    # ambalaj TÜRÜNE (kategoriye) göre değil, food_contact bayrağına göre
    # dahil edilir/çıkarılır (kategori eşleşmesi bunu garanti etmez).
    pfas_reg = next((r for r in regulations if r.code == "PPWR-ART-5"), None)
    if pfas_reg is not None:
        matched = [r for r in matched if r.code != "PPWR-ART-5"]
        if packaging_request.food_contact:
            matched.append(pfas_reg)

    # Var olan değerlendirmeleri temizle (aşama yeniden çalıştırılabilir)
    db.query(RegulatoryAssessment).filter_by(
        packaging_request_id=packaging_request.id
    ).delete()

    food_grade_pcr_exists = (
        db.query(Material)
        .filter(Material.material_type.in_(["pcr", "regranul"]), Material.food_contact_eligible.is_(True))
        .first()
        is not None
    )

    assessments: list[RegulatoryAssessment] = []
    for reg in matched:
        verdict, reasoning = _assess_single_regulation(db, reg, packaging_request, food_grade_pcr_exists)
        row = RegulatoryAssessment(
            packaging_request_id=packaging_request.id,
            regulation_id=reg.id,
            verdict=verdict,
            reasoning=reasoning,
            recyclability_breakdown=_recyclability_breakdown(db, reg),
        )
        db.add(row)
        assessments.append(row)

    overall = _overall_verdict([a.verdict for a in assessments])
    packaging_request.status = PackagingStatus.ASSESSED.value
    db.commit()
    for a in assessments:
        db.refresh(a)
    return overall, assessments


def _overall_verdict(verdicts: list[str]) -> str:
    if any(v == RegulatoryVerdict.NOT_OK.value for v in verdicts):
        return RegulatoryVerdict.NOT_OK.value
    if any(v == RegulatoryVerdict.REVIEW.value for v in verdicts):
        return RegulatoryVerdict.REVIEW.value
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
    return (RegulatoryVerdict.REVIEW.value, "Otomatik değerlendirme kuralı tanımlı değil.")


def _assess_minimization(
    requirements: list[RegulationRequirement], req: PackagingRequest
) -> tuple[str, str]:
    article = requirements[0].article if requirements else "Md.10"
    if not req.dimensions:
        return (
            RegulatoryVerdict.REVIEW.value,
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
    return (
        RegulatoryVerdict.REVIEW.value,
        f"{raw_material_status} | Nihai Ambalaj Uygunluğu: Doğrulama Gerekli — tek bir "
        "hammaddenin sertifikalı olması, nihai ürünün migrasyon/uygunluk testlerinden "
        f"geçtiği anlamına gelmez ({regulation_no}).",
    )


_VERDICT_LABELS: dict[str, str] = {
    RegulatoryVerdict.OK.value: "Uygun Görünüyor",
    RegulatoryVerdict.REVIEW.value: "İnceleme Gerekli",
    RegulatoryVerdict.NOT_OK.value: "Uygun Değil",
}


def _assess_pfas(
    db: Session, reg: Regulation, requirements: list[RegulationRequirement]
) -> tuple[str, str]:
    """PFAS (PPWR Md.5(5)) limitleri artık `ChemicalRestriction` tablosundan
    okunur (Faz F.4) -- eskiden bu sayılar SADECE requirement_text
    prozasında gömülüydü, hiçbir kod okumuyordu. Verdict mantığı DEĞİŞMEDİ
    (hâlâ requirement satırının default_verdict'i), sadece reasoning artık
    gerçek, sorgulanabilir limit değerlerini alıntılıyor."""
    verdict = requirements[0].default_verdict if requirements else RegulatoryVerdict.REVIEW.value
    article = requirements[0].article if requirements else "Md.5(5)"

    restrictions = db.query(ChemicalRestriction).filter_by(regulation_id=reg.id, substance_group="PFAS").all()
    if not restrictions:
        # Referans veri hiç yüklenmemişse (ör. eski bir DB) genel yola düş --
        # sessizce uydurma bir sayı gösterilmez.
        text = requirements[0].requirement_text if requirements else "PFAS limitleri tanımlı değil."
        return verdict, text

    by_type = {r.restriction_type: r for r in restrictions}
    parts = []
    if single := by_type.get("tekil_madde_siniri"):
        parts.append(f"tekil PFAS ≤{single.limit_value:g} {single.limit_unit}")
    if total_target := by_type.get("toplam_hedef"):
        parts.append(f"toplam PFAS ≤{total_target.limit_value:g} {total_target.limit_unit} hedef")
    if total_limit := by_type.get("toplam_sinir"):
        parts.append(f"toplam PFAS ≤{total_limit.limit_value:g} {total_limit.limit_unit} sınır")

    reasoning = (
        f"PFAS Kontrolü — PPWR {article} | "
        f"Gıda temaslı ambalaj olduğu için uygulanır ({', '.join(parts)}) | "
        "Kanıt durumu: Belge/Test Verisi Gerekli | "
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
            RegulatoryVerdict.REVIEW.value,
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
        return RegulatoryVerdict.REVIEW.value, reasoning

    return RegulatoryVerdict.OK.value, reasoning


# --- Aşama 4: Firma Altyapısı ve Otomatik Eşleştirme ----------------------

def match_infrastructure(db: Session, packaging_request: PackagingRequest) -> list[dict]:
    category = canonical_packaging_category(packaging_request.packaging_type)
    lines = (
        db.execute(
            select(ProductionLine).options(selectinload(ProductionLine.material_compatibility))
        )
        .scalars()
        .all()
    )
    results: list[dict] = []
    for line in lines:
        if not line.active:
            continue
        supported_categories = {
            canonical_packaging_category(t) for t in (line.supported_packaging_types or [])
        }
        if category not in supported_categories:
            continue
        compatible_ids = [c.material_id for c in line.material_compatibility]
        reason = (
            f"'{packaging_request.packaging_type}' türü destekleniyor; "
            f"katman yapısı {line.layer_structure}, mikron aralığı "
            f"{line.min_micron:.0f}-{line.max_micron:.0f}, {len(compatible_ids)} uyumlu "
            "hammadde eşleşti."
        )
        results.append({"line": line, "compatible_material_ids": compatible_ids, "match_reason": reason})

    if results:
        packaging_request.status = PackagingStatus.MATCHED.value
        db.commit()
    return results


# --- Aşama 5: Mevcut Reçete / Akıllı Başlangıç ----------------------------

def find_reference_recipe(db: Session, packaging_request: PackagingRequest) -> Recipe | None:
    """Faz B.5: bu case kalıcı bir Ürün/SKU'yu hedefliyorsa (sku_id set),
    referans olarak ÖNCE o SKU'nun current_recipe_id'si denenir — bu, salt
    'aynı packaging_type metni' sezgisel eşleşmesinden daha kesindir (iki
    farklı ürün aynı ambalaj türü metnini paylaşabilir, ama aynı SKU'yu
    paylaşamaz). SKU yoksa ya da current_recipe_id henüz set değilse, eski
    sezgisel eşleşmeye düşülür (geriye dönük uyumlu)."""
    if packaging_request.sku_id and packaging_request.sku and packaging_request.sku.current_recipe_id:
        sku_recipe = db.get(Recipe, packaging_request.sku.current_recipe_id)
        if sku_recipe is not None and sku_recipe.is_verified:
            return sku_recipe

    return (
        db.query(Recipe)
        .join(PackagingRequest)
        .filter(
            PackagingRequest.packaging_type == packaging_request.packaging_type,
            Recipe.is_verified.is_(True),
            Recipe.packaging_request_id != packaging_request.id,
        )
        .order_by(Recipe.version.desc())
        .first()
    )


def generate_initial_recipe(db: Session, packaging_request: PackagingRequest, line: ProductionLine) -> Recipe:
    reference = find_reference_recipe(db, packaging_request)

    if reference is not None:
        recipe = Recipe(
            packaging_request_id=packaging_request.id,
            version=1,
            line_id=line.id,
            source=RecipeSource.REFERANS.value,
            status="taslak",
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
    target_total_micron = (line.min_micron + line.max_micron) / 2

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
        virgin_material = db.query(Material).filter_by(material_type="virgin").first()
    if virgin_material is None:
        raise ValueError("Bilgi tabanında virgin malzeme bulunamadı; önce KB yüklenmeli.")

    recipe = Recipe(
        packaging_request_id=packaging_request.id,
        version=1,
        line_id=line.id,
        source=RecipeSource.URETILDI.value,
        status="taslak",
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
