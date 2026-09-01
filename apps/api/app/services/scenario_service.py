"""Faz P.1 (Madde 20) — "Bu Ambalajı Nasıl Daha İyi Yaparım?" Senaryo
Laboratuvarı: doğrulanmış bir reçete üzerinde what-if hesaplaması.
HİÇBİR ŞEY DB'ye yazılmaz -- saf, istek başına hesap (gerçek üretim
verisiyle asla karıştırılmaz).

Mock bir hesap KURULMADI: gerçek optimizasyon motorunun AYNI parçaları
reuse edilir -- `app/constraint_engine/types.py::RecipeCandidate`/
`LayerCandidate`/`MaterialSpec` (ORM'den bağımsız, saf) ve
`app/optimization/scorer.py::score_candidate()` (maliyet/karbon/mevzuat
marjı skorları, gerçek reçetenin skorlamasında da kullanılan AYNI
fonksiyon). PCR%/kalınlık override'ları, gerçek `Recipe`/`RecipeLayer`
satırları OKUNARAK türetilen bir `RecipeCandidate` kopyası üzerinde
uygulanır -- orijinal ORM nesnesi asla mutate/commit edilmez.

Tüm sonuçlar `"senaryo_simulasyonu"` kind'ıyla etiketlenir (Faz H.3
disiplini) -- bu, Faz I.4/N.1'in TEK Veri Güveni sözlüğüne eklenen YENİ
bir kind'dır (mevcut `simulasyon_verisi` "gerçek üretim beslemesi eksik"
anlamına gelir, hipotetik bir what-if'i KARŞILAMAZ -- bu yüzden ayrı)."""
from dataclasses import replace

from sqlalchemy.orm import Session

from app.constraint_engine.types import LayerCandidate, RecipeCandidate, RegulationSpec
from app.models.company import Facility
from app.models.infrastructure import ProductionLine
from app.models.knowledge import CarbonEmissionFactor, Regulation
from app.models.recipe import Recipe
from app.optimization.scorer import ScoreResult, score_candidate
from app.services.common import find_pcr_target_category, recipe_is_pet_dominant
from app.services.optimization_service import _material_to_spec

# Faz F.1'de seed edilmiş, GERÇEKTEN var olan ama bugüne kadar hiçbir
# serviste kullanılmayan elektrik şebeke karışımı EF'i (bkz.
# knowledge_base/data/carbon_emission_factors.yaml, factor_type=elektrik).
_GRID_ELECTRICITY_FACTOR_TYPE = "elektrik"


def _recipe_to_candidate(recipe: Recipe) -> RecipeCandidate:
    layers = [
        LayerCandidate(
            layer_index=layer.layer_index,
            layer_label=layer.layer_label,
            material=_material_to_spec(layer.material),
            ratio_pct=layer.ratio_pct,
            thickness_micron=layer.thickness_micron,
        )
        for layer in sorted(recipe.layers, key=lambda l: l.layer_index)
    ]
    return RecipeCandidate(layers=layers)


def _apply_thickness_override(candidate: RecipeCandidate, target_micron: float | None) -> RecipeCandidate:
    """Basitleştirme (MVP, dokümante): mevcut katman kalınlık ORANLARI
    korunur, toplam hedefe göre orantılı ölçeklenir -- katman SAYISI/
    sırası/malzemesi değişmez."""
    if target_micron is None:
        return candidate
    baseline_total = candidate.total_micron or 1.0
    scale = target_micron / baseline_total
    return replace(
        candidate,
        layers=[replace(l, thickness_micron=l.thickness_micron * scale) for l in candidate.layers],
    )


def _apply_pcr_override(candidate: RecipeCandidate, target_pcr_pct: float | None) -> tuple[RecipeCandidate, str | None]:
    """Basitleştirme (MVP, dokümante): hedef PCR oranı virgin payından
    karşılanır (regranül payı sabit kalır) -- PCR/virgin katmanlarının
    KALINLIĞI (ratio_pct değil) orantılı olarak yeniden dağıtılır, çünkü bu
    sistemdeki reçeteler pratikte katman başına TEK malzeme taşır
    (ratio_pct=100) -- ratio_pct'i ölçeklemek bu durumda hiçbir etki
    yaratmaz (zaten tavanda). Reçetede PCR-tipi bir malzeme YOKSA (hangi
    malzemeyle karşılanacağı bilinmiyor), mevcut PCR oranı sıfırsa (oransal
    ölçekleme tanımsız) ya da virgin katmanı tamamen tükenmeden hedefe
    ulaşılamıyorsa, bu boyut UYDURULMAZ -- açık bir uyarıyla döner (ikinci
    durumda kısmi/sınırlı sonuçla)."""
    if target_pcr_pct is None:
        return candidate, None
    pcr_idx = [i for i, l in enumerate(candidate.layers) if l.material.material_type == "pcr"]
    virgin_idx = [i for i, l in enumerate(candidate.layers) if l.material.material_type == "virgin"]
    if not pcr_idx:
        return candidate, (
            "Reçetede tanımlı bir PCR malzemesi yok; hedef PCR oranı hangi "
            "malzemeyle karşılanacağı bilinmediğinden PCR senaryosu hesaplanamadı."
        )
    current = candidate.weighted_composition_pct()
    current_pcr = current.get("pcr", 0.0)
    if current_pcr <= 0.01:
        return candidate, "Mevcut PCR oranı sıfıra çok yakın; oransal ölçekleme ile hedefe taşınamıyor."
    if not virgin_idx:
        return candidate, "Reçetede virgin katman yok; PCR oranı artışı virgin payından karşılanamıyor."

    pcr_total_thickness = sum(candidate.layers[i].thickness_micron for i in pcr_idx)
    virgin_total_thickness = sum(candidate.layers[i].thickness_micron for i in virgin_idx)
    pcr_scale = target_pcr_pct / current_pcr
    delta_thickness = pcr_total_thickness * pcr_scale - pcr_total_thickness

    warning = None
    if virgin_total_thickness <= 0:
        return candidate, "Reçetede virgin katman kalınlığı yok; PCR oranı artışı virgin payından karşılanamıyor."
    virgin_scale = 1 - delta_thickness / virgin_total_thickness
    if virgin_scale < 0:
        virgin_scale = 0.0
        warning = (
            f"Hedef PCR oranı %{target_pcr_pct:.0f}, mevcut katman yapısında virgin payı tamamen "
            "tükense bile tam olarak karşılanamıyor -- sonuç yapısal olarak ulaşılabilen en yüksek orana göre hesaplandı."
        )

    new_layers = []
    for i, l in enumerate(candidate.layers):
        if i in pcr_idx:
            new_layers.append(replace(l, thickness_micron=l.thickness_micron * pcr_scale))
        elif i in virgin_idx:
            new_layers.append(replace(l, thickness_micron=max(0.0, l.thickness_micron * virgin_scale)))
        else:
            new_layers.append(l)
    return replace(candidate, layers=new_layers), warning


def _snapshot(
    candidate: RecipeCandidate,
    score: ScoreResult,
    fire_pct: float | None,
    renewable_pct: float | None,
    grid_ef: float | None,
    kind: str,
) -> dict:
    comp = candidate.weighted_composition_pct()
    enerji_karbon_yogunlugu = None
    if grid_ef is not None and renewable_pct is not None:
        enerji_karbon_yogunlugu = round((1 - renewable_pct / 100.0) * grid_ef, 4)
    return {
        "virgin_pct": round(comp.get("virgin", 0.0), 1),
        "pcr_pct": round(comp.get("pcr", 0.0), 1),
        "regranul_pct": round(comp.get("regranul", 0.0), 1),
        "total_micron": round(candidate.total_micron, 1),
        "maliyet_tl_per_kg": score.estimated_cost_per_kg,
        "karbon_kg_co2_per_kg": score.estimated_carbon_kg_co2_per_kg,
        "carbon_ef_status": score.carbon_ef_status,
        "fire_pct": round(fire_pct, 1) if fire_pct is not None else None,
        "yenilenebilir_enerji_pct": round(renewable_pct, 1) if renewable_pct is not None else None,
        # Malzeme karbonundan (karbon_kg_co2_per_kg) AYRI tutulur -- ikisi
        # farklı fiziksel kaynaklardır (bkz. modül docstring'i).
        "enerji_karbon_yogunlugu_kg_co2_per_kwh": enerji_karbon_yogunlugu,
        "veri_kaynagi": kind,
    }


def _technical_risk(
    line: ProductionLine | None,
    target_thickness: float | None,
    pcr_layers_max_ratio: float | None,
    target_pcr_pct: float | None,
) -> dict:
    notlar: list[str] = []
    kalinlik_ok = None
    if line is not None and target_thickness is not None:
        kalinlik_ok = line.min_micron <= target_thickness <= line.max_micron
        if not kalinlik_ok:
            notlar.append(
                f"Hedef kalınlık {target_thickness:.0f}µm, '{line.name}' hattının üretebildiği "
                f"{line.min_micron:.0f}-{line.max_micron:.0f}µm aralığının dışında."
            )
    pcr_tavanini_asiyor_mu = None
    if target_pcr_pct is not None and pcr_layers_max_ratio is not None:
        pcr_tavanini_asiyor_mu = target_pcr_pct > pcr_layers_max_ratio
        if pcr_tavanini_asiyor_mu:
            notlar.append(
                f"Hedef PCR oranı %{target_pcr_pct:.0f}, kullanılan PCR malzemesinin önerilen "
                f"üst sınırı %{pcr_layers_max_ratio:.0f}'i aşıyor."
            )
    return {
        "kalinlik_hat_sinirlari_icinde": kalinlik_ok,
        "pcr_tavanini_asiyor_mu": pcr_tavanini_asiyor_mu,
        "notlar": notlar,
    }


def _regulatory_comparison(
    candidate: RecipeCandidate, regulations: list[RegulationSpec], food_contact: bool, scenario_pcr_pct: float
) -> dict:
    art7 = next((r for r in regulations if r.code == "PPWR-ART-7"), None)
    if art7 is None:
        return {"hedef_pct": None, "hedefi_karsiliyor_mu": None, "not": "PPWR-ART-7 bilgi tabanında tanımlı değil."}
    polymer_codes = [l.material.polymer_code for l in candidate.layers]
    is_pet = recipe_is_pet_dominant(polymer_codes)
    entry = find_pcr_target_category(art7.criteria, food_contact, is_pet)
    if entry is None:
        return {
            "hedef_pct": None, "hedefi_karsiliyor_mu": None,
            "not": "Bu ambalaj kategorisi için PPWR-ART-7 hedefi bilgi tabanında tanımlı değil.",
        }
    hedef = entry.get("by_year", {}).get("2030")
    if hedef is None:
        return {"hedef_pct": None, "hedefi_karsiliyor_mu": None, "not": "2030 hedefi tabloda tanımlı değil."}
    return {"hedef_pct": hedef, "hedefi_karsiliyor_mu": scenario_pcr_pct >= hedef, "not": None}


def run_scenario(db: Session, recipe_id: str, overrides: dict) -> dict | None:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        return None
    if not recipe.is_verified:
        raise ValueError("Senaryo hesaplaması sadece doğrulanmış reçeteler için çalıştırılabilir.")

    baseline_candidate = _recipe_to_candidate(recipe)
    line = db.get(ProductionLine, recipe.line_id) if recipe.line_id else None
    facility = db.get(Facility, line.facility_id) if line is not None and line.facility_id else None

    regulations_orm = db.query(Regulation).all()
    regulations = [
        RegulationSpec(
            code=r.code, title=r.title, category=r.category,
            criteria=r.criteria, applicable_packaging_types=r.applicable_packaging_types,
        )
        for r in regulations_orm
    ]
    food_contact = recipe.packaging_request.food_contact if recipe.packaging_request is not None else False

    grid_ef_row = db.query(CarbonEmissionFactor).filter_by(factor_type=_GRID_ELECTRICITY_FACTOR_TYPE).first()
    grid_ef = grid_ef_row.ef_value if grid_ef_row is not None else None

    baseline_fire_pct = line.average_waste_rate_pct if line is not None else None
    baseline_renewable_pct = facility.renewable_energy_pct if facility is not None else None

    baseline_score = score_candidate(baseline_candidate, regulations, food_contact)
    baseline_snapshot = _snapshot(
        baseline_candidate, baseline_score, baseline_fire_pct, baseline_renewable_pct, grid_ef, kind="hesaplanan"
    )

    scenario_candidate = _apply_thickness_override(baseline_candidate, overrides.get("kalinlik_micron"))
    scenario_candidate, pcr_warning = _apply_pcr_override(scenario_candidate, overrides.get("pcr_pct"))

    scenario_fire_pct = (
        overrides["fire_pct"] if overrides.get("fire_pct") is not None else baseline_fire_pct
    )
    scenario_renewable_pct = (
        overrides["yenilenebilir_enerji_pct"]
        if overrides.get("yenilenebilir_enerji_pct") is not None
        else baseline_renewable_pct
    )

    scenario_score = score_candidate(scenario_candidate, regulations, food_contact)
    scenario_snapshot = _snapshot(
        scenario_candidate, scenario_score, scenario_fire_pct, scenario_renewable_pct, grid_ef,
        kind="senaryo_simulasyonu",
    )

    fark: dict[str, float | None] = {}
    for key in (
        "virgin_pct", "pcr_pct", "regranul_pct", "total_micron",
        "maliyet_tl_per_kg", "karbon_kg_co2_per_kg", "fire_pct",
        "yenilenebilir_enerji_pct", "enerji_karbon_yogunlugu_kg_co2_per_kwh",
    ):
        b, s = baseline_snapshot.get(key), scenario_snapshot.get(key)
        fark[key] = round(s - b, 4) if isinstance(b, (int, float)) and isinstance(s, (int, float)) else None

    max_pcr_ratio = max(
        (l.material.max_recommended_ratio_pct for l in scenario_candidate.layers if l.material.material_type == "pcr"),
        default=None,
    )
    teknik_risk = _technical_risk(
        line, overrides.get("kalinlik_micron"), max_pcr_ratio, overrides.get("pcr_pct")
    )

    mevzuat = _regulatory_comparison(
        scenario_candidate, regulations, food_contact, scenario_snapshot["pcr_pct"]
    )

    return {
        "baseline": baseline_snapshot,
        "senaryo": scenario_snapshot,
        "fark": fark,
        "teknik_risk": teknik_risk,
        "mevzuat": mevzuat,
        "uyarilar": [w for w in [pcr_warning] if w],
    }
