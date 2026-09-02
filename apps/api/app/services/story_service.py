"""Faz S.2 (Madde 30) — Bir Ambalajın Dönüşüm Hikâyesi. Yeni bir hesaplama
YOK -- Faz A-R'de zaten kurulmuş özet fonksiyonları (report_service.py'nin
`_reference_section`/`_selected_recipe_section`/`_physical_verification_
section`/`_production_results_section`/`_regulation_version_history_
section` ve `build_executive_summary`) BİREBİR reuse edilerek sabit 6
aşamalı (Başlangıç/Öneri/Üretim/Doğrulama/Sonuç/Mevzuat) bir anlatıya
dizilir. `build_executive_summary` zaten Faz A'nın "referans varsa yüzde,
yoksa mutlak değer" kuralını uyguluyor -- burada YENİDEN uygulanmaz.

Sadece `recipe.is_verified=True` reçeteler için üretilir -- Madde 30
açıkça "doğrulanmış bir optimizasyon için" diyor, `build_optimization_
report_data()`'nın (report_service.py) ön koşuluyla AYNI."""
from sqlalchemy.orm import Session

from app.models.enums import RecipeSource
from app.models.optimization import OptimizationCandidate
from app.models.recipe import Recipe
from app.services import production_flow_service, traceability_service
from app.services.report_service import (
    _physical_verification_section,
    _production_results_section,
    _reference_section,
    _regulation_version_history_section,
    _selected_recipe_section,
    build_executive_summary,
)


def build_conversion_story(db: Session, recipe_id: str) -> dict | None:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        return None
    if not recipe.is_verified:
        raise ValueError("Bu reçete henüz doğrulanmadı; dönüşüm hikâyesi sadece doğrulanmış reçeteler için üretilir.")

    trace = traceability_service.build_recipe_traceability(db, recipe.id) or {}
    comparison = production_flow_service.build_comparison(db, recipe)
    executive_summary = build_executive_summary(db, recipe, comparison)

    candidate: OptimizationCandidate | None = None
    if recipe.source == RecipeSource.URETILDI.value:
        candidate = db.query(OptimizationCandidate).filter_by(recipe_id=recipe.id).first()

    physical = _physical_verification_section(db, recipe)
    tests = physical["tests"]
    dogrulama = {
        "ozet": {
            "basarili": sum(1 for t in tests if t["result"] == "basarili"),
            "basarisiz": sum(1 for t in tests if t["result"] == "basarisiz"),
            "beklemede": sum(1 for t in tests if t["result"] == "beklemede"),
        },
        "tests": tests,
    }

    uretim = {
        "line": trace.get("machine"),
        "orders": _production_results_section(db, recipe)["orders"],
    }

    return {
        "recipe_id": recipe.id,
        "stages": [
            {"key": "baslangic", "baslik": "Başlangıç", "veri": _reference_section(comparison)},
            {"key": "oneri", "baslik": "Öneri", "veri": _selected_recipe_section(db, recipe, trace, candidate)},
            {"key": "uretim", "baslik": "Üretim", "veri": uretim},
            {"key": "dogrulama", "baslik": "Doğrulama", "veri": dogrulama},
            {"key": "sonuc", "baslik": "Sonuç", "veri": executive_summary},
            {"key": "mevzuat", "baslik": "Mevzuat", "veri": _regulation_version_history_section(db, recipe.packaging_request)},
        ],
    }
