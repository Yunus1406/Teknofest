"""Faz C.5 — Otomatik Optimizasyon Raporu veri toplama servisi. Faz C.5'in
16 bölümü + Faz H.6'nın 5 ek bölümü (toplam 21), çalışmanın DB'de zaten
biriken gerçek verisinden derlenir; hiçbir sayı burada yeniden hesaplanmaz/
uydurulmaz — `production_flow_service.
build_comparison`/`version_history`, `traceability_service.
build_recipe_traceability` (B.9) ve `OptimizationRun.notable_eliminated`
(C.4) burada sadece ÇAĞRILIR, yeniden kurulmaz.

`build_executive_summary()` HEM bu raporun 2. bölümü (Yönetici Özeti) HEM
de standalone "Yönetici Özeti" PDF çıktısının (C.6) tek veri kaynağıdır —
aynı hesap iki kez yazılmaz."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.company import Company, CompanyBenchmark
from app.models.enums import RecipeSource
from app.models.knowledge import Regulation
from app.models.optimization import OptimizationCandidate, OptimizationRun
from app.models.production import PhysicalTest, ProductionOrder, SustainabilityResult, WasteRecord
from app.models.recipe import PackagingRequest, Recipe, RecipeEvaluation, RegulatoryAssessment
from app.models.regulation_requirement import RegulationRequirement
from app.schemas.company import COMPANY_BENCHMARK_METRICS
from app.services import production_flow_service, traceability_service
from app.services.common import canonical_packaging_category
from app.services.packaging_service import _current_requirement_version
from app.services.scorecard_service import build_sustainability_scorecard

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

# Faz H.5 — raporun HİÇBİR bölümünde kaynağı belirsiz/boş bir sayı
# kalmaması için sabit 10 değerli kelime dağarcığı (Firma Verisi/Geçmiş
# Üretim/Makineden Alınan/Simülasyon/Teknik Veri Föyü/Laboratuvar/Mevzuat/
# Hesaplanan/Sistem Referansı/Varsayımsal). Bu, mevcut 3 AYRI sözlüğe
# (DataSourceType/Recipe.data_source_tags/F.12 SourceTier) KARIŞTIRILMAZ --
# sadece raporun gösterimi için o sözlüklerin değerlerini bu dile çeviren
# ince bir köprüdür (aşağıdaki takma adlar bunun için).
_REPORT_SOURCE_LABELS = {
    # H.5'in kendi 10 değerli kelime dağarcığı (birebir anahtar).
    "firma_verisi": "Firma Verisi",
    "gecmis_uretim": "Geçmiş Üretim",
    "makineden_alinan": "Makineden Alınan",
    "simulasyon": "Simülasyon",
    "teknik_veri_foyu": "Teknik Veri Föyü",
    "laboratuvar": "Laboratuvar",
    "mevzuat": "Mevzuat",
    "hesaplanan": "Hesaplanan",
    "sistem_referansi": "Sistem Referansı",
    "varsayimsal": "Varsayımsal",
    # DataSourceType (app/models/enums.py) takma adları.
    "gecmis_uretim_verisi": "Geçmiş Üretim",
    "simulasyon_verisi": "Simülasyon",
    "laboratuvar_testi": "Laboratuvar",
    "kullanici_girisi": "Firma Verisi",
    # carbon_ef_status (app/services/carbon.py) takma adları --
    # "tanimlanmadi" KASITLI OLARAK burada YOK: gerçekten kaynağı bilinmeyen
    # bir EF, "Varsayımsal" bile değildir, dürüstçe "Veri Yok" kalmalı.
    "tanimli_gercek": "Sistem Referansı",
    "tanimli_demo": "Varsayımsal",
}


def report_source_label(kind: str | None) -> str:
    """Faz H.5 — `kind` (mevcut herhangi bir kaynak sinyali: DataSourceType
    slug'ı, carbon_ef_status, ya da H.5'in kendi 10 değerli anahtarlarından
    biri) gerçekten belirlenemiyorsa (None) ya da tanınmıyorsa 'Veri Yok'
    döner -- ASLA rastgele/varsayılan bir kaynak uydurulmaz."""
    if kind is None:
        return "Veri Yok"
    return _REPORT_SOURCE_LABELS.get(kind, "Veri Yok")


# Faz I.4 — Sistem geneli "Veri Güveni" göstergesi. AYRI bir hesaplama
# DEĞİL -- `_REPORT_SOURCE_LABELS` ile AYNI `kind` girdi kümesini 4 kademeli
# bir ölçeğe (Yüksek/Orta/Düşük/Varsayımsal) çevirir. F.12'nin öncelik
# sırasıyla (FIRMA_OLCUM/FIRMA_URETIM en güvenilir -> VARSAYIM en az) tutarlı:
# doğrudan ölçüm/makine verisi Yüksek, firma geçmişi/tedarikçi föyü/hesaplama
# Orta, mevzuat/sistem referansı/simülasyon Düşük, varsayımsal/demo en alt.
_CONFIDENCE_BY_KIND = {
    "makineden_alinan": "Yüksek",
    "laboratuvar": "Yüksek",
    "firma_verisi": "Yüksek",
    "laboratuvar_testi": "Yüksek",
    "kullanici_girisi": "Yüksek",
    # Faz N.1a — Faz G.4'ün 5 kademeli firma hafızası tier'ları
    # (apps/web/src/lib/labels.ts::_CONFIDENCE_BY_SOURCE_KIND ile senkron
    # tutulmalı, bkz. oradaki yorum).
    "ayni_sku": "Yüksek",
    "ayni_ambalaj_turu": "Yüksek",
    "benzer_kullanim_alani": "Orta",
    "benzer_teknik_sartlar": "Orta",
    "ayni_hat": "Düşük",
    "gecmis_uretim": "Orta",
    "teknik_veri_foyu": "Orta",
    "hesaplanan": "Orta",
    "gecmis_uretim_verisi": "Orta",
    "mevzuat": "Düşük",
    "sistem_referansi": "Düşük",
    "simulasyon": "Düşük",
    "simulasyon_verisi": "Düşük",
    "tanimli_gercek": "Düşük",
    "varsayimsal": "Varsayımsal",
    "tanimli_demo": "Varsayımsal",
}


def data_confidence_level(kind: str | None) -> str | None:
    """Kaynak gerçekten belirlenemiyorsa (None ya da tanınmıyorsa) None
    döner -- rozet HİÇ gösterilmez (report_source_label'ın 'Veri Yok'
    döndüğü durumla aynı disiplin, burada sadece rozetin kendisi basılmaz)."""
    if kind is None:
        return None
    return _CONFIDENCE_BY_KIND.get(kind)


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
        return {"has_reference": False, "note": _NO_REFERENCE_NOTE, "reference": None, "_kaynak": None, "_guven": None}
    # Referans, firma hafızasındaki daha önce ÜRETİLMİŞ+doğrulanmış bir
    # reçetedir (bkz. production_flow_service.build_comparison) -- "Geçmiş
    # Üretim" gerçek kaynağı, uydurulmuyor.
    return {
        "has_reference": True,
        "note": None,
        "reference": reference_side,
        "_kaynak": report_source_label("gecmis_uretim"),
        "_guven": data_confidence_level("gecmis_uretim"),
    }


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
        # Faz H.5 — katman/kalınlık dağılımı optimizasyon motorunun
        # deterministik çıktısıdır -- "Hesaplanan".
        "_kaynak": report_source_label("hesaplanan"),
        "_guven": data_confidence_level("hesaplanan"),
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


def _regulation_version_history_section(db: Session, packaging_request: PackagingRequest | None) -> dict:
    """Faz L.4 (Madde 17) — bu reçetenin mevzuat değerlendirmelerinde
    GERÇEKTEN KULLANILAN versiyon(lar) (`RegulatoryAssessment.
    regulation_version_snapshot`, assessment ANINDA dondurulur, Faz L.3) +
    güncel versiyondan farklıysa değişiklik özeti. `ppwr_on_uyum` bölümünün
    `requirement_version`'ı ile KARIŞTIRILMAMALI -- o HER ZAMAN güncel
    versiyonu gösterir, bu bölüm ise "o an ne kullanıldı" sorusuna cevap
    verir."""
    if packaging_request is None:
        return {"items": []}
    assessments = db.query(RegulatoryAssessment).filter_by(packaging_request_id=packaging_request.id).all()
    items = []
    for a in assessments:
        reg = db.get(Regulation, a.regulation_id)
        current_version = _current_requirement_version(db, a.regulation_id)
        changed = (
            a.regulation_version_snapshot is not None
            and current_version is not None
            and a.regulation_version_snapshot != current_version
        )
        change_summary = None
        if changed:
            row = (
                db.query(RegulationRequirement)
                .filter_by(regulation_id=a.regulation_id)
                .order_by(RegulationRequirement.target_year)
                .first()
            )
            change_summary = row.change_summary if row else None
        items.append(
            {
                "regulation_code": reg.code if reg is not None else None,
                "used_version": a.regulation_version_snapshot,
                "current_version": current_version,
                "changed_since_assessment": changed,
                "change_summary": change_summary,
                "assessed_at": a.created_at,
            }
        )
    return {"items": items}


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
        # Faz H.5 — kompozisyon/karbon reçeteden HESAPLANIR; fire/enerji
        # ise Faz H.3'ün per_1000'e zaten kaydettiği GERÇEK kaynağı taşır
        # (bugün her zaman simülasyon, uydurulmuyor).
        "_kaynak_kompozisyon": report_source_label("hesaplanan"),
        "_kaynak_fire_enerji": report_source_label((per_1000 or {}).get("fire_enerji_veri_kaynagi")),
        "_guven_kompozisyon": data_confidence_level("hesaplanan"),
        "_guven_fire_enerji": data_confidence_level((per_1000 or {}).get("fire_enerji_veri_kaynagi")),
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
                    # Faz J.1 — Test 9: kaynak değişimi rapora yansımalı.
                    "version": ef.get("version"),
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


# --- Faz H.6 — Optimizasyon Raporuna Ek Bölümler ----------------------------

_METHODOLOGY_TEXT = (
    "Kütle Dengesi: 1.000 satılabilir ambalaj başına virgin/PCR/PIR-regranül/"
    "karbon kg -- alan (uzunluk × genişlik) × toplam kalınlık × katman bazlı "
    "ağırlıklı yoğunluk × birim sayısı (bkz. app/services/mass_balance.py "
    "compute_mass_breakdown). Karbon: her katmandaki malzemenin emisyon "
    "faktörü (kg CO2e/kg) katman ağırlığıyla çarpılıp toplanır (bkz. "
    "app/services/carbon.py resolve_carbon_ef). Optimizasyon Skoru: teknik "
    "performans, üretilebilirlik, mevzuat marjı, karbon, fire riski ve "
    "maliyetin ağırlıklı ortalaması (bkz. app/optimization/scorer.py). "
    "Fiziksel Doğrulama: gerçek laboratuvar ölçümü ile tanımlı hedef aralığın "
    "karşılaştırılması -- kriter tanımsızsa sonuç asla otomatik 'başarılı' "
    "sayılmaz, 'beklemede' kalır (bkz. production_flow_service._evaluate_"
    "physical_test)."
)


def _methodology_section() -> dict:
    return {"aciklama": _METHODOLOGY_TEXT}


def _bibliography_section(data_traceability: dict) -> dict:
    """Faz H.6 — Faz F kütüphanelerinden otomatik derlenir; `_data_
    traceability_section`'ın zaten topladığı veriden (yeniden sorgu YOK)."""
    return {
        "mevzuat_versiyonlari": data_traceability["regulation_requirement_versions"],
        "karbon_ef_kaynaklari": data_traceability["carbon_ef_sources"],
    }


def _data_quality_section(db: Session, recipe: Recipe, sustainability_per_1000: dict | None, data_traceability: dict) -> dict:
    """Faz H.6 — hangi değerlerin yüksek/orta/düşük güvenilirlikte, hangileri
    varsayımsal olduğuna dair özet. Hiçbir yeni hesap YOK -- var olan
    `RecipeEvaluation.data_confidence` (kısıt motoru/optimizasyon) ve
    `is_demo_placeholder`/`karbon_veri_kalitesi` (Faz F/H.3) alanlarının
    agregasyonu."""
    evaluations = db.query(RecipeEvaluation).filter_by(recipe_id=recipe.id).all()
    confidence_dagilimi: dict[str, int] = {}
    for e in evaluations:
        if e.data_confidence:
            confidence_dagilimi[e.data_confidence] = confidence_dagilimi.get(e.data_confidence, 0) + 1
    demo_ef_sayisi = sum(1 for ef in data_traceability["carbon_ef_sources"] if ef.get("is_demo_placeholder"))
    return {
        "data_confidence_dagilimi": confidence_dagilimi,
        "karbon_veri_kalitesi": (sustainability_per_1000 or {}).get("karbon_veri_kalitesi"),
        "demo_varsayimsal_ef_sayisi": demo_ef_sayisi,
        "toplam_karbon_ef_sayisi": len(data_traceability["carbon_ef_sources"]),
    }


def _assumptions_section(data_traceability: dict, sustainability_per_1000: dict | None) -> dict:
    """Faz H.6 — GERÇEKTEN varsayımsal işaretlenmiş kalemlerin listesi;
    hiçbiri yoksa boş liste (uydurma bir varsayım ASLA eklenmez)."""
    items: list[str] = []
    for ef in data_traceability["carbon_ef_sources"]:
        if ef.get("is_demo_placeholder"):
            material_name = ef.get("material_name") or "Bilinmeyen malzeme"
            items.append(f"{material_name}: karbon emisyon faktörü DEMO/VARSAYIMSAL (kaynaklı bir LCA veritabanı entegrasyonu yok)")
    if (sustainability_per_1000 or {}).get("karbon_veri_kalitesi") == "tanimli_demo":
        items.append("Toplam karbon figürü en az bir DEMO/VARSAYIMSAL emisyon faktörüne dayanıyor")
    return {"items": items, "has_assumptions": len(items) > 0}


def _source_matrix_section(data: dict) -> list[dict]:
    """Faz H.5'in her bölüme eklediği kaynak etiketlerinin TEK bir özet
    tablosu -- rapordaki her ana rakamın nereden geldiği bir bakışta
    görünür. `data`, bu fonksiyon çağrılana kadar inşa edilmiş TÜM diğer
    bölümleri içerir; burada hiçbir yeni sorgu/hesap YAPILMAZ. Faz I.4 —
    her satıra, AYNI `_guven` alanlarından (varsa) bir "Veri Güveni"
    sütunu da eklenir."""
    rows: list[dict] = []
    if data["referans_recete"].get("_kaynak"):
        rows.append({"alan": "Referans Reçete", "kaynak": data["referans_recete"]["_kaynak"], "guven": data["referans_recete"].get("_guven")})
    if data["secilen_recete"].get("_kaynak"):
        rows.append({"alan": "Seçilen Reçete (katman/kalınlık)", "kaynak": data["secilen_recete"]["_kaynak"], "guven": data["secilen_recete"].get("_guven")})
    if data["tahmini_sonuclar"].get("_kaynak"):
        rows.append({"alan": "Tahmini Sonuçlar (Aşama 8)", "kaynak": data["tahmini_sonuclar"]["_kaynak"], "guven": data["tahmini_sonuclar"].get("_guven")})
    per_1000 = data["surdurulebilirlik_performansi"]["per_1000_units"] or {}
    if per_1000.get("kutle_veri_kaynagi"):
        rows.append({"alan": "Gerçekleşen Virgin/PCR/PIR-Regranül/Karbon", "kaynak": report_source_label(per_1000["kutle_veri_kaynagi"]), "guven": data_confidence_level(per_1000["kutle_veri_kaynagi"])})
    if per_1000.get("fire_enerji_veri_kaynagi"):
        rows.append({"alan": "Gerçekleşen Fire/Enerji", "kaynak": report_source_label(per_1000["fire_enerji_veri_kaynagi"]), "guven": data_confidence_level(per_1000["fire_enerji_veri_kaynagi"])})
    if data["iklim_dongusellik"].get("_kaynak_kompozisyon"):
        rows.append({"alan": "İklim/Döngüsellik Kompozisyon", "kaynak": data["iklim_dongusellik"]["_kaynak_kompozisyon"], "guven": data["iklim_dongusellik"].get("_guven_kompozisyon")})
    if data["iklim_dongusellik"].get("_kaynak_fire_enerji"):
        rows.append({"alan": "İklim/Döngüsellik Fire/Enerji", "kaynak": data["iklim_dongusellik"]["_kaynak_fire_enerji"], "guven": data["iklim_dongusellik"].get("_guven_fire_enerji")})
    for t in data["fiziksel_dogrulama"]["tests"]:
        rows.append({"alan": f"Fiziksel Test: {t['test_type']}", "kaynak": report_source_label(t.get("source")), "guven": data_confidence_level(t.get("source"))})
    for o in data["gercek_uretim_sonuclari"]["orders"]:
        if o.get("data_source"):
            rows.append({"alan": "Gerçek Üretim Sonuçları", "kaynak": report_source_label(o["data_source"]), "guven": data_confidence_level(o["data_source"])})
    for i in data["ppwr_on_uyum"]["items"]:
        if i.get("requirement_source"):
            rows.append({"alan": f"PPWR {i.get('article') or i.get('regulation_code')}", "kaynak": "Mevzuat", "guven": data_confidence_level("mevzuat")})
    return rows


# Faz N.2 (Madde 15) — CompanyBenchmark.metric_name -> comparison["recommended"]
# içindeki AYNI büyüklüğü taşıyan alan (bkz. production_flow_service.py
# _composition_side). Reçetenin GERÇEK, sistemin zaten hesapladığı değeri
# ile kıyaslanır -- ayrı bir hesap YAPILMAZ.
_BENCHMARK_METRIC_TO_RECOMMENDED_FIELD = {
    "karbon_kg_co2_per_kg": "carbon_kg_co2_per_kg",
    "maliyet_tl_per_kg": "cost_per_kg",
    "pcr_orani_pct": "pcr_pct",
}


def _benchmark_comparison_section(db: Session, packaging_request: PackagingRequest | None, comparison: dict) -> dict:
    """Faz N.2 (Madde 15) — SADECE kullanıcının Firma Profili'nden gerçekten
    girdiği `CompanyBenchmark` satırları kullanılır (bkz. app/models/
    company.py::CompanyBenchmark). Firma yoksa, bu kategori için hiç
    benchmark girilmemişse, `available: False` döner -- hiçbir zaman bir
    sektör ortalaması sentezlenmez/enterpole edilmez; çağıran taraf
    (PDF/frontend) bunu açıkça "Benchmark: Veri Yok" olarak göstermelidir."""
    if packaging_request is None:
        return {"available": False}
    company = db.query(Company).first()
    if company is None:
        return {"available": False}
    category = canonical_packaging_category(packaging_request.packaging_type)
    rows = (
        db.query(CompanyBenchmark)
        .filter_by(company_id=company.id, packaging_category=category)
        .order_by(CompanyBenchmark.metric_name)
        .all()
    )
    if not rows:
        return {"available": False, "packaging_category": category}

    recommended = comparison["recommended"]
    items = []
    for row in rows:
        recipe_field = _BENCHMARK_METRIC_TO_RECOMMENDED_FIELD.get(row.metric_name)
        recipe_value = recommended.get(recipe_field) if recipe_field else None
        fark_pct = None
        if recipe_value is not None and row.value:
            fark_pct = round(((recipe_value - row.value) / row.value) * 100, 1)
        items.append(
            {
                "metric_name": row.metric_name,
                "metric_label": COMPANY_BENCHMARK_METRICS.get(row.metric_name, row.metric_name),
                "benchmark_value": row.value,
                "benchmark_unit": row.unit,
                "benchmark_source": row.source,
                "benchmark_entered_at": row.created_at.isoformat(),
                "recete_degeri": recipe_value,
                "fark_pct": fark_pct,
            }
        )
    return {"available": True, "packaging_category": category, "items": items}


def build_optimization_report_data(db: Session, recipe_id: str) -> dict:
    """Faz C.5'in 16 bölümü + Faz H.6'nın 5 ek bölümü. Sadece `recipe.is_verified=True` reçeteler için
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
    data_traceability = _data_traceability_section(production_section, physical_section, ppwr_section, trace)

    result = {
        "kapak": _cover(recipe, packaging_request, run, trace),
        "yonetici_ozeti": executive_summary,
        "ambalaj_bilgileri": _packaging_info(packaging_request) if packaging_request is not None else None,
        "referans_recete": _reference_section(comparison),
        "optimizasyon_sureci": _optimization_process_section(recipe, run),
        "neden_elendi": _elimination_section(recipe, run),
        "secilen_recete": _selected_recipe_section(recipe, trace),
        # Faz H.5 — comparison["recommended"] paylaşılan bir sözlük (Aşama
        # 8'in kendi API yanıtında da kullanılıyor); burada YENİ bir kopya
        # (spread) üzerine `_kaynak` eklenir, orijinal dict MUTATE edilmez.
        "tahmini_sonuclar": {
            **comparison["recommended"],
            "_kaynak": report_source_label("hesaplanan"),
            "_guven": data_confidence_level("hesaplanan"),
        },
        "gercek_uretim_sonuclari": production_section,
        "fiziksel_dogrulama": physical_section,
        "surdurulebilirlik_performansi": sustainability_section,
        "ppwr_on_uyum": ppwr_section,
        "iklim_dongusellik": _climate_circularity_section(comparison, sustainability_section["per_1000_units"]),
        "veri_izlenebilirligi": data_traceability,
        "recete_izlenebilirligi": production_flow_service.version_history(db, recipe),
        "sonuc": _conclusion_section(executive_summary),
        # --- Faz H.6 — ek bölümler (mevcut 16 anahtarın hiçbiri değişmedi) ---
        "hesaplama_metodolojisi": _methodology_section(),
        "kaynakca": _bibliography_section(data_traceability),
        "veri_kalitesi_notu": _data_quality_section(db, recipe, sustainability_section["per_1000_units"], data_traceability),
        "kullanilan_varsayimlar": _assumptions_section(data_traceability, sustainability_section["per_1000_units"]),
        # Faz L.4 — mevcut hiçbir anahtar değişmedi, additive.
        "mevzuat_versiyon_gecmisi": _regulation_version_history_section(db, packaging_request),
        # Faz N.2 (Madde 15) — mevcut hiçbir anahtar değişmedi, additive.
        "sektore_gore_konum": _benchmark_comparison_section(db, packaging_request, comparison),
        # Faz O.2 (Madde 19) — mevcut hiçbir anahtar değişmedi, additive.
        # `comparison`/`executive_summary` zaten hesaplanmış, yeniden sorgu
        # YOK (bkz. scorecard_service.py modül docstring'i).
        "surdurulebilirlik_karnesi": build_sustainability_scorecard(db, recipe, comparison, executive_summary),
    }
    result["veri_kaynagi_matrisi"] = _source_matrix_section(result)
    return result
