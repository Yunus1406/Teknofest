"""Aşama 6-7 orkestrasyonu — bu fazın asıl teslimatı: kısıt motoru +
optimizasyon + LLM gerekçelendirmeyi tek bir koşuda birleştirir, sonucu
kalıcı olarak DB'ye yazar (Recipe + evaluations + metrics + optimization
run/candidates) ve API'ye dönecek OptimizationRunOut'u üretir."""
from sqlalchemy.orm import Session

from app.constraint_engine.engine import filter_candidates
from app.constraint_engine.types import (
    EvaluationContext,
    LineSpec,
    MaterialSpec,
    PackagingContext,
    RecipeCandidate,
    RegulationSpec,
)
from app.models.enums import DataSourceType, EvaluationTier, MetricType, RecipeSource
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Regulation
from app.models.optimization import OptimizationCandidate, OptimizationRun
from app.models.recipe import PackagingRequest, Recipe, RecipeEvaluation, RecipeLayer, RecipeMetric
from app.llm.justification import build_elimination_summary, build_finalist_justification
from app.optimization.candidate_generator import LayerMaterialOptions, generate_candidates
from app.optimization.scorer import score_candidate
from app.services.carbon import resolve_carbon_ef
from app.services.common import canonical_packaging_category, preferred_polymer_codes

MAX_FINALISTS = 4
MAX_NOTABLE_ELIMINATED = 3


def _material_to_spec(m: Material) -> MaterialSpec:
    carbon_value, carbon_status, carbon_source = resolve_carbon_ef(m)
    return MaterialSpec(
        id=m.id,
        name=m.name,
        polymer_code=m.polymer.code,
        material_type=m.material_type,
        food_contact_eligible=m.food_contact_eligible,
        max_recommended_ratio_pct=m.max_recommended_ratio_pct,
        degradation_factor=m.degradation_factor,
        mfi_g_10min=m.mfi_g_10min,
        cost_per_kg=m.cost_per_kg,
        carbon_factor_kg_co2_per_kg=carbon_value,
        carbon_ef_status=carbon_status,
        carbon_ef_source=carbon_source,
    )


def _line_to_spec(line: ProductionLine) -> LineSpec:
    material_max_ratio = {c.material_id: c.max_ratio_pct for c in line.material_compatibility}
    return LineSpec(
        id=line.id,
        name=line.name,
        layer_structure=line.layer_structure,
        layer_count=line.layer_count,
        min_micron=line.min_micron,
        max_micron=line.max_micron,
        min_gsm=line.min_gsm,
        max_gsm=line.max_gsm,
        supported_packaging_types=line.supported_packaging_types,
        material_max_ratio=material_max_ratio,
    )


def _build_layer_options(
    db: Session, line: ProductionLine, packaging_request: PackagingRequest
) -> list[LayerMaterialOptions]:
    preferred = preferred_polymer_codes(packaging_request.packaging_type)
    compatible_ids = {c.material_id for c in line.material_compatibility}
    labels = line.layer_structure.split("/")

    options: list[LayerMaterialOptions] = []
    for label in labels:
        query = db.query(Material)
        if compatible_ids:
            query = query.filter(Material.id.in_(compatible_ids))
        candidates = query.filter(Material.material_type == "virgin").all()
        # tercih sırasına göre en uygun virgin malzemeyi seç
        virgin = None
        for code in preferred:
            for c in candidates:
                if c.polymer.code == code:
                    virgin = c
                    break
            if virgin:
                break
        if virgin is None and candidates:
            virgin = candidates[0]
        if virgin is None:
            continue  # bu katman için hiç uygun virgin malzeme yok, atla

        recycled_query = db.query(Material).filter(
            Material.polymer_id == virgin.polymer_id,
            Material.material_type.in_(["pcr", "regranul"]),
        )
        if compatible_ids:
            recycled_query = recycled_query.filter(Material.id.in_(compatible_ids))
        recycled = recycled_query.all()

        options.append(
            LayerMaterialOptions(
                layer_label=label,
                virgin=_material_to_spec(virgin),
                recycled_options=[_material_to_spec(m) for m in recycled],
            )
        )
    return options


def _decision_basis(line: ProductionLine, regulations: list[RegulationSpec]) -> dict:
    return {
        "gecmis_receteler": [],  # Faz 1: geçmiş doğrulanmış reçete yok
        "mevzuat_maddeleri": [r.code for r in regulations],
        "hat_parametreleri": {
            "hat": line.name,
            "katman_yapisi": line.layer_structure,
            "mikron_araligi": f"{line.min_micron:.0f}-{line.max_micron:.0f}",
        },
    }


def _persist_finalist(
    db: Session,
    packaging_request: PackagingRequest,
    line: ProductionLine,
    run: OptimizationRun,
    rank: int,
    candidate: RecipeCandidate,
    score,
    regulations: list[RegulationSpec],
    target_volume_units: int,
) -> OptimizationCandidate:
    recipe = Recipe(
        packaging_request_id=packaging_request.id,
        version=1,
        line_id=line.id,
        source=RecipeSource.URETILDI.value,
        status="onerildi",
        total_micron=candidate.total_micron,
    )
    db.add(recipe)
    db.flush()

    for layer in candidate.layers:
        db.add(
            RecipeLayer(
                recipe_id=recipe.id,
                layer_index=layer.layer_index,
                layer_label=layer.layer_label,
                material_id=layer.material.id,
                ratio_pct=layer.ratio_pct,
                thickness_micron=layer.thickness_micron,
            )
        )

    db.add(
        RecipeEvaluation(
            recipe_id=recipe.id,
            tier=EvaluationTier.TAHMINI_FIZIKSEL_PERFORMANS.value,
            verdict="gecti",
            reason_code="optimizasyon_skoru",
            reason_text=(
                f"Kısıt motorundan geçti; çok kriterli optimizasyon skoru "
                f"{score.total:.2f} (0-1 arası) ile {rank}. sırada."
            ),
            data_confidence=score.data_confidence,
        )
    )

    composition = candidate.weighted_composition_pct()
    kg_per_1000_units = 1.0  # basitleştirilmiş varsayım: birim ürün ~ katman ağırlığı oranlı
    total_kg_estimate = (target_volume_units / 1000.0) * kg_per_1000_units if target_volume_units else 0.0
    metrics = [
        (MetricType.VIRGIN_USAGE, composition.get("virgin", 0.0), "%"),
        (MetricType.PCR_USAGE, composition.get("pcr", 0.0), "%"),
        (MetricType.REGRANULE_USAGE, composition.get("regranul", 0.0), "%"),
        (MetricType.CARBON, score.estimated_carbon_kg_co2_per_kg, "kg_co2/kg"),
        (MetricType.COST, score.estimated_cost_per_kg, "TL/kg"),
    ]
    for metric_type, value, unit in metrics:
        db.add(
            RecipeMetric(
                recipe_id=recipe.id,
                metric_type=metric_type.value,
                value=value,
                unit=unit,
                is_estimated=True,
                data_source_type=DataSourceType.HESAPLANAN.value,
            )
        )

    justification_data = {
        "composition_pct": composition,
        "score": score.total,
        "score_breakdown": score.breakdown,
        "data_confidence": score.data_confidence,
        "decision_basis": _decision_basis(line, regulations),
    }
    justification_text = build_finalist_justification(justification_data)

    opt_candidate = OptimizationCandidate(
        run_id=run.id,
        recipe_id=recipe.id,
        score=score.total,
        rank=rank,
        is_finalist=True,
        score_breakdown=score.breakdown,
        carbon_data_quality=score.carbon_ef_status,
        justification_text=justification_text,
        decision_basis=_decision_basis(line, regulations),
    )
    db.add(opt_candidate)
    db.flush()
    return opt_candidate


def _eliminated_summary(candidate: RecipeCandidate, violations: list) -> dict:
    composition = candidate.weighted_composition_pct()
    reasons = [v.reason_text for v in violations]
    return {
        "composition_summary": (
            f"%{composition.get('virgin', 0):.0f} virgin / %{composition.get('pcr', 0):.0f} PCR / "
            f"%{composition.get('regranul', 0):.0f} regranül, toplam {candidate.total_micron:.0f} mikron"
        ),
        "reasons": reasons,
        "summary_text": build_elimination_summary(reasons),
    }


def run_optimization(
    db: Session, packaging_request_id: str, line_id: str, ratio_step_pct: int = 10
) -> dict:
    packaging_request = db.get(PackagingRequest, packaging_request_id)
    if packaging_request is None:
        raise ValueError("Ambalaj talebi bulunamadı")
    line = db.get(ProductionLine, line_id)
    if line is None:
        raise ValueError("Üretim hattı bulunamadı")

    regulations_orm = db.query(Regulation).all()
    regulations = [
        RegulationSpec(
            code=r.code,
            title=r.title,
            category=r.category,
            criteria=r.criteria,
            applicable_packaging_types=r.applicable_packaging_types,
        )
        for r in regulations_orm
    ]

    layer_options = _build_layer_options(db, line, packaging_request)
    if not layer_options:
        raise ValueError(
            "Bu hat için bilgi tabanında uygun hammadde bulunamadı; önce KB/hat eşleştirmesi kontrol edin."
        )

    line_spec = _line_to_spec(line)
    candidates = generate_candidates(line_spec, layer_options, ratio_step_pct=ratio_step_pct)

    ctx = EvaluationContext(
        packaging=PackagingContext(
            packaging_type=canonical_packaging_category(packaging_request.packaging_type),
            food_contact=packaging_request.food_contact,
            target_volume_units=packaging_request.target_volume_units,
        ),
        line=line_spec,
        regulations=regulations,
    )
    survivors, eliminated = filter_candidates(candidates, ctx)

    scored = [
        (c, score_candidate(c, regulations, food_contact=packaging_request.food_contact))
        for c in survivors
    ]
    scored.sort(key=lambda pair: pair[1].total, reverse=True)
    finalists = scored[:MAX_FINALISTS]

    run = OptimizationRun(
        packaging_request_id=packaging_request.id,
        parameters={
            "ratio_step_pct": ratio_step_pct,
            "candidate_count_generated": len(candidates),
            "survived_constraint_engine_count": len(survivors),
        },
    )
    db.add(run)
    db.flush()

    finalist_rows = []
    for rank, (candidate, score) in enumerate(finalists, start=1):
        row = _persist_finalist(
            db,
            packaging_request,
            line,
            run,
            rank,
            candidate,
            score,
            regulations,
            packaging_request.target_volume_units,
        )
        finalist_rows.append(row)

    # En "yakın ıskalayan" (en az ihlalli) elenenleri öne çıkar
    eliminated_sorted = sorted(eliminated, key=lambda pair: len(pair[1]))
    notable_eliminated = [
        _eliminated_summary(c, violations) for c, violations in eliminated_sorted[:MAX_NOTABLE_ELIMINATED]
    ]

    # Faz C.4 — zaten hesaplanan bu listeyi kalıcı hale getir (Rapor §6 için).
    run.notable_eliminated = notable_eliminated

    packaging_request.status = "recete_hazir"
    db.commit()

    return {
        "run": run,
        "finalist_candidate_ids": [row.id for row in finalist_rows],
        "notable_eliminated": notable_eliminated,
        "generated_candidate_count": len(candidates),
        "survived_constraint_engine_count": len(survivors),
    }
