"""Faz P.2 (Madde 21) — Otomatik Eko-Tasarım Önerileri. HER öneri GERÇEK
veriden türetilir (mevcut `RecipeLayer`/`Material`/`ProductionLine`/
`RegulatoryAssessment` satırlarından); jenerik/şablon bir öneri metni ASLA
üretilmez. Yeterli veri/eşik yoksa o öneri türü HİÇ üretilmez -- boş bir
liste dönmesi hata değil, dürüst bir sonuçtur (bkz. her fonksiyonun kendi
docstring'i)."""
from sqlalchemy.orm import Session

from app.models.infrastructure import ProductionLine
from app.models.knowledge import Regulation
from app.models.recipe import Recipe, RecipeAdditive, RegulatoryAssessment
from app.models.recyclability_criterion import RecyclabilityCriterion


def _suggestion(key: str, title: str, detay_metni: str, veri_guveni_kind: str) -> dict:
    return {"key": key, "title": title, "detay_metni": detay_metni, "veri_guveni_kind": veri_guveni_kind}


def _kalinlik_azaltma(recipe: Recipe, line: ProductionLine | None) -> dict | None:
    if line is None or not recipe.total_micron or recipe.total_micron <= line.min_micron:
        return None
    marj = recipe.total_micron - line.min_micron
    return _suggestion(
        "kalinlik_azaltma", "Kalınlık Azaltma Potansiyeli",
        f"Toplam kalınlık {recipe.total_micron:.0f}µm, atanmış '{line.name}' hattının üretebildiği alt "
        f"sınır {line.min_micron:.0f}µm — {marj:.0f}µm'e kadar azaltma teorik olarak hat sınırları "
        "içinde kalır (fiziksel doğrulama testi gerektirir).",
        "hesaplanan",
    )


def _mono_material(db: Session, recipe: Recipe) -> dict | None:
    polymer_codes = sorted({
        l.material.polymer.code for l in recipe.layers if l.material is not None and l.material.polymer is not None
    })
    if len(polymer_codes) <= 1:
        return None
    detay = (
        f"Bu reçete {len(polymer_codes)} farklı polimer ailesi kullanıyor ({', '.join(polymer_codes)}). "
        "Tek polimere (mono-material) dönüşüm geri dönüştürülebilirliği kolaylaştırabilir."
    )
    # Faz F.9'un GERÇEK kriter metni varsa eklenir (numerik bir puan İDDİA EDİLMEZ).
    criterion = db.query(RecyclabilityCriterion).filter_by(dimension="tasarim_uyumu").first()
    if criterion is not None:
        detay += f" İlgili kriter: {criterion.criterion_text}"
    return _suggestion("mono_material_donusum", "Mono-Material Dönüşüm Fırsatı", detay, "hesaplanan")


def _pcr_artirma(recipe: Recipe) -> list[dict]:
    suggestions = []
    for l in recipe.layers:
        if l.material is None or l.material.material_type != "pcr":
            continue
        cap = l.material.max_recommended_ratio_pct
        if cap is None or l.ratio_pct >= cap - 0.5:
            continue
        suggestions.append(
            _suggestion(
                f"pcr_artirma_katman_{l.layer_index}", "PCR Artırma Potansiyeli",
                f"Katman {l.layer_label}'deki {l.material.name} PCR oranı %{l.ratio_pct:.0f}, malzemenin "
                f"önerilen üst sınırı %{cap:.0f} — %{cap - l.ratio_pct:.0f} artış teorik olarak mümkün.",
                "hesaplanan",
            )
        )
    return suggestions


def _gereksiz_katman(recipe: Recipe) -> dict | None:
    material_ids = [l.material_id for l in recipe.layers]
    dup_ids = {mid for mid in material_ids if material_ids.count(mid) > 1}
    if not dup_ids:
        return None
    labels = sorted({l.layer_label for l in recipe.layers if l.material_id in dup_ids})
    return _suggestion(
        "gereksiz_katman_azaltimi", "Gereksiz Katman Azaltımı",
        f"{', '.join(labels)} katmanları AYNI malzemeyi kullanıyor — birleştirilmesi katman sayısını "
        "azaltabilir (proses/ekstrüzyon uygunluğu doğrulanmalıdır).",
        "hesaplanan",
    )


def _masterbatch_optimizasyonu(db: Session, recipe: Recipe) -> list[dict]:
    suggestions = []
    for a in db.query(RecipeAdditive).filter_by(recipe_id=recipe.id).all():
        if a.additive is None or not a.additive.dosage_max_pct:
            continue
        if a.dosage_pct >= a.additive.dosage_max_pct * 0.9:
            suggestions.append(
                _suggestion(
                    f"masterbatch_{a.id}", "Renk/Masterbatch Optimizasyonu",
                    f"{a.additive.name} dozajı %{a.dosage_pct:.1f}, önerilen üst sınıra "
                    f"(%{a.additive.dosage_max_pct:.1f}) yakın/eşit — düşürme fırsatı değerlendirilebilir.",
                    "hesaplanan",
                )
            )
    return suggestions


def _geri_donusturulebilirlik(db: Session, recipe: Recipe) -> list[dict]:
    if recipe.packaging_request is None:
        return []
    assessment = (
        db.query(RegulatoryAssessment)
        .join(Regulation, RegulatoryAssessment.regulation_id == Regulation.id)
        .filter(
            RegulatoryAssessment.packaging_request_id == recipe.packaging_request_id,
            Regulation.code == "PPWR-ART-6",
        )
        .first()
    )
    if assessment is None or assessment.recyclability_breakdown is None:
        return []
    suggestions = []
    for d in assessment.recyclability_breakdown.get("dimensions", []):
        suggestions.append(
            _suggestion(
                f"geri_donusturulebilirlik_{d['dimension']}", "Geri Dönüştürülebilirlik İyileştirmesi",
                d["criterion_text"], "mevzuat",
            )
        )
    return suggestions


def build_eco_design_suggestions(db: Session, recipe: Recipe) -> list[dict]:
    line = db.get(ProductionLine, recipe.line_id) if recipe.line_id else None
    suggestions: list[dict] = []
    for s in (_kalinlik_azaltma(recipe, line), _mono_material(db, recipe), _gereksiz_katman(recipe)):
        if s is not None:
            suggestions.append(s)
    suggestions.extend(_pcr_artirma(recipe))
    suggestions.extend(_masterbatch_optimizasyonu(db, recipe))
    suggestions.extend(_geri_donusturulebilirlik(db, recipe))
    return suggestions
