"""Faz Q.1 (Madde 23) — Üretim Öncesi Risk Skoru. 7 bileşen, HER biri
GERÇEK, zaten hesaplanan/1 sorguyla ulaşılabilir veriden türetilir; yeni
bir ML/opak model KURULMAZ. Şeffaf: hangi bileşenin riski yükselttiği her
zaman görünür (Faz P.3'ün açıklanabilirlik ilkesiyle tutarlı). Hiçbir şey
persist edilmez -- Faz O/P'nin "compute-on-read" disipliniyle aynı, her
istek DB'nin güncel halinden taze hesaplanır."""
from sqlalchemy.orm import Session

from app.constraint_engine.types import RegulationSpec
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Regulation
from app.models.recipe import Recipe, RecipeLayer
from app.optimization.scorer import score_candidate
from app.services.packaging_service import (
    build_food_contact_evidence_checklist,
    find_reference_recipe_with_evidence,
    match_infrastructure,
)
from app.services.scenario_service import _recipe_to_candidate


def _component(deger, risk_katkisi: str, aciklama: str) -> dict:
    return {"deger": deger, "risk_katkisi": risk_katkisi, "aciklama": aciklama}


def _yeni_hammadde_bileseni(db: Session, recipe: Recipe) -> dict:
    yeni_malzemeler = []
    for layer in recipe.layers:
        used_before = (
            db.query(RecipeLayer)
            .join(Recipe, RecipeLayer.recipe_id == Recipe.id)
            .filter(
                RecipeLayer.material_id == layer.material_id,
                Recipe.is_verified.is_(True),
                Recipe.id != recipe.id,
            )
            .first()
        )
        if used_before is None and layer.material is not None:
            yeni_malzemeler.append(layer.material.name)
    if yeni_malzemeler:
        return _component(
            yeni_malzemeler, "yuksek",
            f"{', '.join(yeni_malzemeler)} daha önce hiçbir doğrulanmış reçetede kullanılmamış.",
        )
    return _component([], "dusuk", "Tüm hammaddeler daha önce doğrulanmış reçetelerde kullanılmış.")


def _pcr_seviyesi_bileseni(pcr_pct: float) -> dict:
    if pcr_pct >= 40:
        risk = "yuksek"
    elif pcr_pct >= 15:
        risk = "orta"
    else:
        risk = "dusuk"
    return _component(round(pcr_pct, 1), risk, f"PCR oranı %{pcr_pct:.0f}.")


def _kalinlik_azaltimi_bileseni(recipe: Recipe, reference: Recipe | None) -> dict:
    if reference is None or not reference.total_micron or not recipe.total_micron:
        return _component(None, "dusuk", "Referans reçete bulunamadı; kalınlık sapması değerlendirilemiyor.")
    sapma_pct = round(((reference.total_micron - recipe.total_micron) / reference.total_micron) * 100, 1)
    if sapma_pct >= 15:
        risk = "yuksek"
    elif sapma_pct >= 5:
        risk = "orta"
    else:
        risk = "dusuk"
    yon = "azaltılmış" if sapma_pct > 0 else "artırılmış" if sapma_pct < 0 else "değiştirilmemiş"
    return _component(sapma_pct, risk, f"Referansa göre kalınlık %{abs(sapma_pct):.0f} {yon}.")


def _makine_uyumu_bileseni(db: Session, packaging_request, line: ProductionLine | None) -> dict:
    if packaging_request is None or line is None:
        return _component(None, "orta", "Üretim hattı henüz atanmadı.")
    matches = match_infrastructure(db, packaging_request)
    entry = next((m for m in matches if m["line"].id == line.id), None)
    if entry is None:
        return _component(None, "orta", "Hat uygunluk skoru hesaplanamadı.")
    score_pct = entry["score_pct"]
    if score_pct < 60:
        risk = "yuksek"
    elif score_pct < 85:
        risk = "orta"
    else:
        risk = "dusuk"
    return _component(score_pct, risk, f"'{line.name}' hattı uygunluk skoru %{score_pct:.0f}.")


def _gecmis_uretim_benzerligi_bileseni(evidence_count: int, tier: str | None) -> dict:
    if tier is None:
        return _component(0, "yuksek", "Firma hafızasında benzer bir doğrulanmış üretim bulunamadı.")
    risk = "dusuk" if tier in ("ayni_sku", "ayni_ambalaj_turu") else "orta"
    return _component(evidence_count, risk, f"{evidence_count} doğrulanmış benzer üretim bulundu ({tier}).")


def _teknik_performans_bileseni(teknik_performans_skoru: float) -> dict:
    if teknik_performans_skoru < 0.5:
        risk = "yuksek"
    elif teknik_performans_skoru < 0.75:
        risk = "orta"
    else:
        risk = "dusuk"
    return _component(round(teknik_performans_skoru, 2), risk, f"Tahmini teknik performans skoru {teknik_performans_skoru:.2f}.")


def _mevzuat_kanit_bileseni(checklist: list[dict]) -> dict:
    eksik = [i for i in checklist if i["status"] == "eksik"]
    if not eksik:
        return _component(0, "dusuk", "Gıda teması kanıt listesinde eksik kalem yok (ya da gıda teması yok).")
    if len(eksik) >= 3:
        risk = "yuksek"
    else:
        risk = "orta"
    return _component(len(eksik), risk, f"{len(eksik)} gıda teması kanıt kalemi eksik.")


_RISK_ORDER = {"dusuk": 0, "orta": 1, "yuksek": 2}


def _genel_risk(components: dict) -> str:
    seviyeler = [c["risk_katkisi"] for c in components.values()]
    if any(s == "yuksek" for s in seviyeler):
        return "yuksek"
    if sum(1 for s in seviyeler if s == "orta") >= 2:
        return "orta"
    return "dusuk"


def compute_risk_score(db: Session, recipe: Recipe) -> dict:
    packaging_request = recipe.packaging_request
    line = db.get(ProductionLine, recipe.line_id) if recipe.line_id else None
    candidate = _recipe_to_candidate(recipe)
    composition = candidate.weighted_composition_pct()

    reference = None
    evidence_count = 0
    tier = None
    checklist: list[dict] = []
    if packaging_request is not None:
        ref_result = find_reference_recipe_with_evidence(db, packaging_request, recipe.line_id)
        reference = ref_result.recipe
        evidence_count = ref_result.evidence_count
        tier = ref_result.tier
        checklist = build_food_contact_evidence_checklist(db, packaging_request)

    food_contact = packaging_request.food_contact if packaging_request is not None else False
    regulations = [
        RegulationSpec(
            code=r.code, title=r.title, category=r.category,
            criteria=r.criteria, applicable_packaging_types=r.applicable_packaging_types,
        )
        for r in db.query(Regulation).all()
    ]
    score = score_candidate(candidate, regulations, food_contact)

    components = {
        "yeni_hammadde": _yeni_hammadde_bileseni(db, recipe),
        "pcr_seviyesi": _pcr_seviyesi_bileseni(composition.get("pcr", 0.0)),
        "kalinlik_azaltimi": _kalinlik_azaltimi_bileseni(recipe, reference),
        "makine_uyumu": _makine_uyumu_bileseni(db, packaging_request, line),
        "gecmis_uretim_benzerligi": _gecmis_uretim_benzerligi_bileseni(evidence_count, tier),
        "teknik_performans": _teknik_performans_bileseni(score.breakdown["teknik_performans"]),
        "mevzuat_kanit_eksikleri": _mevzuat_kanit_bileseni(checklist),
    }
    return {"genel_risk": _genel_risk(components), "bilesenler": components}
