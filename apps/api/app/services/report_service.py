"""Faz C.5 — Otomatik Optimizasyon Raporu veri toplama servisi. 16 bölümün
TAMAMI, çalışmanın DB'de zaten biriken gerçek verisinden derlenir; hiçbir
sayı burada yeniden hesaplanmaz/uydurulmaz — `production_flow_service.
build_comparison`/`version_history`, `traceability_service.
build_recipe_traceability` (B.9) ve `OptimizationRun.notable_eliminated`
(C.4) burada sadece ÇAĞRILIR, yeniden kurulmaz.

`build_executive_summary()` HEM bu raporun 2. bölümü (Yönetici Özeti) HEM
de standalone "Yönetici Özeti" PDF çıktısının (C.6) tek veri kaynağıdır —
aynı hesap iki kez yazılmaz."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.enums import RecipeSource
from app.models.knowledge import Regulation
from app.models.optimization import OptimizationCandidate, OptimizationRun
from app.models.production import PhysicalTest, ProductionOrder, SustainabilityResult, WasteRecord
from app.models.recipe import PackagingRequest, Recipe, RegulatoryAssessment
from app.models.regulation_requirement import RegulationRequirement
from app.services import production_flow_service, traceability_service

_PPWR_DISCLAIMER = (
    "Bu değerlendirme mevzuat ön uyum karar desteğidir; hukuki uygunluk "
    "sertifikasyonu değildir."
)
_NO_REFERENCE_NOTE = "Doğrulanmış referans bulunmamaktadır."
_NO_RUN_SOURCE_NOTE = "Bu reçete bir optimizasyon koşusundan değil, mevcut referanstan geldi."
_NO_RUN_FOUND_NOTE = "Bu reçete için ilişkili bir optimizasyon koşusu bulunamadı."
_NO_ELIMINATED_DATA_NOTE = (
    "Bu çalışma için elenen aday detayı kaydedilmedi (Faz C.4 öncesi bir koşu olabilir)."
)


def _find_reference_recipe(db: Session, recipe: Recipe) -> Recipe | None:
    """`production_flow_service.build_comparison()`'daki referans seçim
    sorgusunun AYNISI — bilinçli küçük bir tekrar. build_comparison sadece
    kompozisyon-özet dict'i (`reference_side`) döner, id taşımaz; burada
    referansın KENDİ SustainabilityResult'ını bulabilmek için gerçek Recipe
    nesnesine ihtiyaç var. production_flow_service DEĞİŞTİRİLMEDİ."""
    if recipe.packaging_request is None:
        return None
    return (
        db.query(Recipe)
        .join(PackagingRequest)
        .filter(
            PackagingRequest.packaging_type == recipe.packaging_request.packaging_type,
            Recipe.is_verified.is_(True),
            Recipe.id != recipe.id,
        )
        .order_by(Recipe.version.desc())
        .first()
    )


def _sustainability_result_for(db: Session, recipe_id: str) -> dict | None:
    row = (
        db.query(SustainabilityResult)
        .filter_by(recipe_id=recipe_id, is_actual=True)
        .order_by(SustainabilityResult.created_at.desc())
        .first()
    )
    return row.per_1000_units if row is not None else None


def _pct_reduction(old: float | None, new: float | None) -> float | None:
    """Düşüş iyi olan metrikler için (virgin, hammadde, fire, enerji, karbon,
    maliyet). Referans/eski değer yoksa ya da sıfırsa None -- asla 0 veya
    uydurma bir yüzdeye düşülmez."""
    if old is None or new is None or old == 0:
        return None
    return round(((old - new) / old) * 100, 1)


def _pct_increase(old: float | None, new: float | None) -> float | None:
    """Artış iyi olan metrikler için (PCR)."""
    if old is None or new is None or old == 0:
        return None
    return round(((new - old) / old) * 100, 1)


def _fmt_pct(v: float | None) -> str:
    return f"%{abs(v):.1f}" if v is not None else "—"


def build_executive_summary(db: Session, recipe: Recipe, comparison: dict) -> dict:
    reference_side = comparison["reference"]
    recommended_side = comparison["recommended"]

    if reference_side is None:
        absolute = _sustainability_result_for(db, recipe.id)
        return {
            "has_reference": False,
            "gains_pct": None,
            "realized_absolute_per_1000_units": absolute,
            "narrative": (
                "Doğrulanmış bir referans reçete bulunmadığından iyileşme yüzdesi "
                "hesaplanmadı; aşağıdaki rakamlar 1.000 satılabilir ambalaj başına "
                "GERÇEKLEŞEN mutlak performanstır."
            ),
        }

    # Hammadde/fire/enerji: SADECE her iki reçete de gerçekten üretilip
    # (finalize_result ile) kendi gerçek per-1000-units verisini bırakmışsa
    # karşılaştırılır -- Aşama 8'in TAHMİNİ verisiyle GERÇEKLEŞEN veri asla
    # karıştırılmaz. Reçetelerden biri hiç üretilmediyse bu üç kalem "—" kalır.
    reference_recipe = _find_reference_recipe(db, recipe)
    recommended_actual = _sustainability_result_for(db, recipe.id)
    reference_actual = _sustainability_result_for(db, reference_recipe.id) if reference_recipe else None

    def _num(d: dict | None, key: str) -> float | None:
        v = (d or {}).get(key)
        return v if isinstance(v, (int, float)) else None

    hammadde_azaltimi_pct = fire_azaltimi_pct = enerji_azaltimi_pct = None
    if recommended_actual and reference_actual:
        ref_parts = [_num(reference_actual, k) for k in ("virgin_kg", "pcr_kg", "regranul_kg")]
        new_parts = [_num(recommended_actual, k) for k in ("virgin_kg", "pcr_kg", "regranul_kg")]
        ref_hammadde = sum(p for p in ref_parts if p is not None) if any(p is not None for p in ref_parts) else None
        new_hammadde = sum(p for p in new_parts if p is not None) if any(p is not None for p in new_parts) else None
        hammadde_azaltimi_pct = _pct_reduction(ref_hammadde, new_hammadde)
        fire_azaltimi_pct = _pct_reduction(_num(reference_actual, "fire_kg"), _num(recommended_actual, "fire_kg"))
        enerji_azaltimi_pct = _pct_reduction(_num(reference_actual, "enerji_kwh"), _num(recommended_actual, "enerji_kwh"))

    comparison_gains = comparison.get("gains") or {}
    gains_pct = {
        "virgin_azalimi_pct": _pct_reduction(reference_side["virgin_pct"], recommended_side["virgin_pct"]),
        "pcr_artisi_pct": _pct_increase(reference_side["pcr_pct"], recommended_side["pcr_pct"]),
        "hammadde_azaltimi_pct": hammadde_azaltimi_pct,
        "fire_azaltimi_pct": fire_azaltimi_pct,
        "enerji_azaltimi_pct": enerji_azaltimi_pct,
        "karbon_azaltimi_pct": comparison_gains.get("karbon_azaltimi_pct"),
        "maliyet_azaltimi_pct": comparison_gains.get("maliyet_azaltimi_pct"),
    }

    narrative = " | ".join(
        [
            f"Virgin ↓ {_fmt_pct(gains_pct['virgin_azalimi_pct'])}",
            f"PCR ↑ {_fmt_pct(gains_pct['pcr_artisi_pct'])}",
            f"Hammadde ↓ {_fmt_pct(gains_pct['hammadde_azaltimi_pct'])}",
            f"Fire ↓ {_fmt_pct(gains_pct['fire_azaltimi_pct'])}",
            f"Enerji ↓ {_fmt_pct(gains_pct['enerji_azaltimi_pct'])}",
            f"Karbon ↓ {_fmt_pct(gains_pct['karbon_azaltimi_pct'])}",
            f"Maliyet ↓ {_fmt_pct(gains_pct['maliyet_azaltimi_pct'])}",
        ]
    )

    return {
        "has_reference": True,
        "gains_pct": gains_pct,
        "realized_absolute_per_1000_units": recommended_actual,
        "narrative": narrative,
    }


def _cover(
    recipe: Recipe, packaging_request: PackagingRequest | None, run: OptimizationRun | None, trace: dict
) -> dict:
    return {
        "company_name": trace["company"]["name"] if trace.get("company") else None,
        "sku_code": trace["sku"]["sku_code"] if trace.get("sku") else None,
        "product_name": (
            trace["sku"]["product_name"] if trace.get("sku") else (packaging_request.product if packaging_request else None)
        ),
        "optimization_run_id": run.id if run is not None else None,
        "recipe_id": recipe.id,
        "recipe_version": recipe.version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _packaging_info(packaging_request: PackagingRequest) -> dict:
    return {
        "packaging_type": packaging_request.packaging_type,
        "usage_area": packaging_request.usage_area,
        "product": packaging_request.product,
        "dimensions": packaging_request.dimensions,
        "target_market": packaging_request.target_market,
        "food_contact": packaging_request.food_contact,
        "target_volume_units": packaging_request.target_volume_units,
    }


def _reference_section(comparison: dict) -> dict:
    reference_side = comparison["reference"]
    if reference_side is None:
        return {"has_reference": False, "note": _NO_REFERENCE_NOTE, "reference": None}
    return {"has_reference": True, "note": None, "reference": reference_side}


def _optimization_process_section(recipe: Recipe, run: OptimizationRun | None) -> dict:
    if recipe.source == RecipeSource.REFERANS.value:
        return {"applicable": False, "note": _NO_RUN_SOURCE_NOTE}
    if run is None:
        return {"applicable": False, "note": _NO_RUN_FOUND_NOTE}
    return {
        "applicable": True,
        "note": None,
        "ratio_step_pct": run.parameters.get("ratio_step_pct"),
        "generated_candidate_count": run.parameters.get("candidate_count_generated"),
        "survived_constraint_engine_count": run.parameters.get("survived_constraint_engine_count"),
        "finalist_count": len(run.candidates),
    }


def _elimination_section(recipe: Recipe, run: OptimizationRun | None) -> dict:
    if recipe.source == RecipeSource.REFERANS.value:
        return {"applicable": False, "note": _NO_RUN_SOURCE_NOTE, "items": []}
    if run is None:
        return {"applicable": False, "note": _NO_RUN_FOUND_NOTE, "items": []}
    if not run.notable_eliminated:
        return {"applicable": True, "note": _NO_ELIMINATED_DATA_NOTE, "items": []}
    return {"applicable": True, "note": None, "items": run.notable_eliminated}


def _selected_recipe_section(recipe: Recipe, trace: dict) -> dict:
    return {
        "version": recipe.version,
        "status": recipe.status,
        "is_verified": recipe.is_verified,
        "total_micron": recipe.total_micron,
        "total_gsm": recipe.total_gsm,
        "line_name": trace["machine"]["name"] if trace.get("machine") else None,
        "layers": trace.get("layers", []),
    }


def _production_results_section(db: Session, recipe: Recipe) -> dict:
    orders = db.query(ProductionOrder).filter_by(recipe_id=recipe.id).all()
    order_rows = []
    for order in orders:
        live_rows = order.live_data
        total_produced = max((r.produced_qty_units for r in live_rows), default=0)
        total_energy = max((r.cumulative_energy_kwh for r in live_rows), default=0.0)
        total_waste = max((r.cumulative_waste_kg for r in live_rows), default=0.0)
        avg_speed = round(sum(r.line_speed_m_min for r in live_rows) / len(live_rows), 1) if live_rows else None

        material_consumption_kg: dict[str, float] = {}
        for r in live_rows:
            for material_id, kg in (r.material_consumption or {}).items():
                material_consumption_kg[material_id] = material_consumption_kg.get(material_id, 0.0) + kg

        waste_by_type_kg: dict[str, float] = {}
        for w in db.query(WasteRecord).filter_by(production_order_id=order.id).all():
            waste_by_type_kg[w.waste_type] = waste_by_type_kg.get(w.waste_type, 0.0) + w.kg

        duration_minutes = None
        if order.actual_start and order.actual_end:
            duration_minutes = round((order.actual_end - order.actual_start).total_seconds() / 60, 1)

        order_rows.append(
            {
                "id": order.id,
                "status": order.status,
                "operator": order.operator,
                "scheduled_qty_units": order.scheduled_qty_units,
                "total_produced_units": total_produced,
                "duration_minutes": duration_minutes,
                "avg_line_speed_m_min": avg_speed,
                "total_energy_kwh": round(total_energy, 3),
                "total_waste_kg": round(total_waste, 3),
                "material_consumption_kg": {k: round(v, 3) for k, v in material_consumption_kg.items()},
                "waste_by_type_kg": {k: round(v, 3) for k, v in waste_by_type_kg.items()},
                "data_source": live_rows[0].source if live_rows else None,
            }
        )
    return {"orders": order_rows}


def _physical_verification_section(db: Session, recipe: Recipe) -> dict:
    tests = db.query(PhysicalTest).filter_by(recipe_id=recipe.id).all()
    return {
        "tests": [
            {
                "test_type": t.test_type,
                "value": t.value,
                "unit": t.unit,
                "target_min": t.target_min,
                "target_max": t.target_max,
                "test_method": t.test_method,
                "result": t.result,
                "passed": t.passed,
                "source": t.source,
            }
            for t in tests
        ]
    }


def _ppwr_section(db: Session, packaging_request: PackagingRequest | None) -> dict:
    if packaging_request is None:
        return {"items": [], "disclaimer": _PPWR_DISCLAIMER}
    assessments = db.query(RegulatoryAssessment).filter_by(packaging_request_id=packaging_request.id).all()
    items = []
    for a in assessments:
        reg = db.get(Regulation, a.regulation_id)
        requirement = (
            db.query(RegulationRequirement).filter_by(regulation_id=a.regulation_id).first()
            if reg is not None
            else None
        )
        items.append(
            {
                "regulation_code": reg.code if reg is not None else None,
                "article": requirement.article if requirement is not None else None,
                "verdict": a.verdict,
                "reasoning": a.reasoning,
                "requirement_version": requirement.version if requirement is not None else None,
                "requirement_source": requirement.source if requirement is not None else None,
                "exception_text": requirement.exception_text if requirement is not None else None,
            }
        )
    return {"items": items, "disclaimer": _PPWR_DISCLAIMER}


# Faz C.5 — "İklim ve Döngüsellik Perspektifi" KASITLI olarak kavramsal bir
# çerçeve etiketidir. Burada ya da raporun hiçbir yerinde "COP31 Uyumlu"
# gibi doğrulanmamış bir uygunluk/sertifikasyon iddiası ÜRETİLMEZ — buna
# dayanak (bağımsız bir COP31 uygunluk değerlendirmesi/sertifikasyonu) yok.
def _climate_circularity_section(comparison: dict, per_1000: dict | None) -> dict:
    recommended_side = comparison["recommended"]
    reference_side = comparison["reference"]
    return {
        "perspective_label": "İklim ve Döngüsellik Perspektifi",
        "virgin_pct": recommended_side["virgin_pct"],
        "pcr_pct": recommended_side["pcr_pct"],
        "regranule_pct": recommended_side["regranule_pct"],
        "carbon_kg_co2_per_kg": recommended_side["carbon_kg_co2_per_kg"],
        "carbon_data_quality": recommended_side["carbon_data_quality"],
        "fire_kg_per_1000": (per_1000 or {}).get("fire_kg"),
        "enerji_kwh_per_1000": (per_1000 or {}).get("enerji_kwh"),
        "has_reference_trend": reference_side is not None,
        "reference_virgin_pct": reference_side["virgin_pct"] if reference_side else None,
        "reference_pcr_pct": reference_side["pcr_pct"] if reference_side else None,
    }


def _data_traceability_section(
    production_section: dict, physical_section: dict, ppwr_section: dict, trace: dict
) -> dict:
    carbon_sources = []
    for layer in trace.get("layers", []):
        ef = layer.get("carbon_ef")
        if ef:
            carbon_sources.append(
                {
                    "material_name": layer["material"]["name"] if layer.get("material") else None,
                    "ef_value": ef["ef_value"],
                    "unit": ef["unit"],
                    "is_demo_placeholder": ef["is_demo_placeholder"],
                    "source": ef["source"],
                }
            )
    return {
        "production_data_sources": sorted({o["data_source"] for o in production_section["orders"] if o["data_source"]}),
        "physical_test_sources": sorted({t["source"] for t in physical_section["tests"] if t["source"]}),
        "carbon_ef_sources": carbon_sources,
        "regulation_requirement_versions": [
            {
                "regulation_code": i["regulation_code"],
                "version": i["requirement_version"],
                "source": i["requirement_source"],
            }
            for i in ppwr_section["items"]
        ],
    }


def _conclusion_section(executive_summary: dict) -> dict:
    return {"summary_text": executive_summary["narrative"]}


def build_optimization_report_data(db: Session, recipe_id: str) -> dict:
    """16 bölümün tamamı. Sadece `recipe.is_verified=True` reçeteler için
    çağrılabilir (Dashboard 12'nin doğal uzantısı — aynı ön koşul DPP ile
    aynı, bkz. app/services/passport_service.py)."""
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise ValueError("Reçete bulunamadı")
    if not recipe.is_verified:
        raise ValueError("Optimizasyon raporu sadece doğrulanmış reçeteler için oluşturulabilir")

    packaging_request = recipe.packaging_request
    trace = traceability_service.build_recipe_traceability(db, recipe.id) or {}
    comparison = production_flow_service.build_comparison(db, recipe)

    run: OptimizationRun | None = None
    if recipe.source == RecipeSource.URETILDI.value:
        candidate = db.query(OptimizationCandidate).filter_by(recipe_id=recipe.id).first()
        if candidate is not None:
            run = db.get(OptimizationRun, candidate.run_id)

    production_section = _production_results_section(db, recipe)
    physical_section = _physical_verification_section(db, recipe)
    ppwr_section = _ppwr_section(db, packaging_request)
    sustainability_section = {"per_1000_units": _sustainability_result_for(db, recipe.id)}
    executive_summary = build_executive_summary(db, recipe, comparison)

    return {
        "kapak": _cover(recipe, packaging_request, run, trace),
        "yonetici_ozeti": executive_summary,
        "ambalaj_bilgileri": _packaging_info(packaging_request) if packaging_request is not None else None,
        "referans_recete": _reference_section(comparison),
        "optimizasyon_sureci": _optimization_process_section(recipe, run),
        "neden_elendi": _elimination_section(recipe, run),
        "secilen_recete": _selected_recipe_section(recipe, trace),
        "tahmini_sonuclar": comparison["recommended"],
        "gercek_uretim_sonuclari": production_section,
        "fiziksel_dogrulama": physical_section,
        "surdurulebilirlik_performansi": sustainability_section,
        "ppwr_on_uyum": ppwr_section,
        "iklim_dongusellik": _climate_circularity_section(comparison, sustainability_section["per_1000_units"]),
        "veri_izlenebilirligi": _data_traceability_section(production_section, physical_section, ppwr_section, trace),
        "recete_izlenebilirligi": production_flow_service.version_history(db, recipe),
        "sonuc": _conclusion_section(executive_summary),
    }
