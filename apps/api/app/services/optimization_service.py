"""Aşama 6-7 orkestrasyonu — bu fazın asıl teslimatı: kısıt motoru +
optimizasyon + LLM gerekçelendirmeyi tek bir koşuda birleştirir, sonucu
kalıcı olarak DB'ye yazar (Recipe + evaluations + metrics + optimization
run/candidates) ve API'ye dönecek OptimizationRunOut'u üretir."""
from sqlalchemy.orm import Session

from app.constraint_engine.engine import filter_candidates
from app.constraint_engine.rules import validate_recipe_math_consistency
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
from app.optimization.candidate_generator import (
    LayerMaterialOptions,
    describe_candidate_generation,
    generate_candidates,
)
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
        carbon_ef_version=m.carbon_ef.version if m.carbon_ef is not None else None,
        technical_datasheet_ref=m.technical_datasheet_ref,
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


def _decision_basis(
    line: ProductionLine,
    regulations: list[RegulationSpec],
    candidate: RecipeCandidate,
    reference_evidence: dict | None,
) -> dict:
    """Faz G.5 — `gecmis_receteler` artık GERÇEKTEN doluyor (Faz G.4'ün
    Aşama 5'te bu ambalaj talebi için bulduğu kanıttan, bkz. run_optimization);
    eskiden burada her zaman sabit `[]` vardı ("Faz 1: geçmiş doğrulanmış
    reçete yok" yorumuyla). `hammadde_veri_foyu_sayisi`/`karbon_ef_versiyonu`
    YENİ alanlar -- ADAYIN GERÇEK katmanlarından türetilir, uydurulmaz."""
    datasheet_count = sum(1 for layer in candidate.layers if layer.material.technical_datasheet_ref)
    carbon_versions = sorted({
        layer.material.carbon_ef_version for layer in candidate.layers if layer.material.carbon_ef_version
    })
    return {
        "gecmis_receteler": reference_evidence["candidate_recipe_ids"] if reference_evidence else [],
        "gecmis_recete_kademe": reference_evidence["tier"] if reference_evidence else None,
        "mevzuat_maddeleri": [r.code for r in regulations],
        "hat_parametreleri": {
            "hat": line.name,
            "katman_yapisi": line.layer_structure,
            "mikron_araligi": f"{line.min_micron:.0f}-{line.max_micron:.0f}",
        },
        "hammadde_veri_foyu_sayisi": datasheet_count,
        "karbon_ef_versiyonu": carbon_versions[0] if carbon_versions else None,
    }


def compute_data_source_tags(candidate: RecipeCandidate, decision_basis: dict) -> list[str]:
    """Faz G.5 — bir reçetenin GERÇEKTEN hangi veri kaynaklarından
    beslendiğini işaretler. `firma_verisi`/`makineden_alinan`/`laboratuvar`
    bu fonksiyonda KASITLI OLARAK asla eklenmez -- Aşama 7'nin adayları henüz
    üretilmemiştir, bu üç etiket ancak Aşama 10-12'de gerçek üretim/lab
    verisi bağlandığında anlamlı olur (bkz. app/models/enums.py
    DataSourceType'ın aynı disiplini)."""
    tags: list[str] = ["hesaplanan"]  # skorlama hesaplaması her zaman bir katkı
    if decision_basis.get("gecmis_receteler"):
        tags.append("gecmis_uretim")
    if any(layer.material.technical_datasheet_ref for layer in candidate.layers):
        tags.append("teknik_veri_foyu")
    if decision_basis.get("mevzuat_maddeleri"):
        tags.append("mevzuat")
    carbon_statuses = {layer.material.carbon_ef_status for layer in candidate.layers}
    if carbon_statuses & {"tanimlanmadi", "tanimli_demo"}:
        tags.append("varsayimsal")
    return tags


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
    reference_evidence: dict | None,
) -> OptimizationCandidate:
    # Faz K.7 (Madde 9) — reçete üretim zincirine (persist) girmeden önce
    # matematiksel tutarlılığı doğrulanır. Bu, iş kuralı elemesi DEĞİL
    # (constraint_engine zaten o işi filter_candidates'te yaptı) -- bir
    # matematik hatasına karşı son bir güvenlik ağı (ör. katman kalınlığı
    # toplamının hedeften sapması).
    consistency_failures = validate_recipe_math_consistency(
        candidate, target_total_micron=packaging_request.target_thickness_micron
    )
    if consistency_failures:
        raise ValueError(
            "Reçete matematiksel olarak tutarsız, üretim zincirine giremez: "
            + "; ".join(consistency_failures)
        )

    decision_basis = _decision_basis(line, regulations, candidate, reference_evidence)
    data_source_tags = compute_data_source_tags(candidate, decision_basis)

    recipe = Recipe(
        packaging_request_id=packaging_request.id,
        version=1,
        line_id=line.id,
        source=RecipeSource.URETILDI.value,
        status="onerildi",
        total_micron=candidate.total_micron,
        data_source_tags=data_source_tags,
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
        "decision_basis": decision_basis,
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
        decision_basis=decision_basis,
    )
    db.add(opt_candidate)
    db.flush()
    return opt_candidate


def _eliminated_summary(candidate: RecipeCandidate, violations: list) -> dict:
    """Faz J.0 — `reasons` artık düz metin değil, her elemenin GERÇEK
    `EvaluationTier`'ını (kesin_teknik_kisit/malzeme_proses_kisiti) taşıyan
    yapılandırılmış bir liste -- Dashboard 6'nın 'Neden Elendi?' bölümü bu
    ikisini yapısal olarak ayırt edebilsin diye (önceden sadece serbest
    metinde görünüyordu, tier bilgisi burada düşürülüyordu)."""
    composition = candidate.weighted_composition_pct()
    reason_texts = [v.reason_text for v in violations]
    return {
        "composition_summary": (
            f"%{composition.get('virgin', 0):.0f} virgin / %{composition.get('pcr', 0):.0f} PCR / "
            f"%{composition.get('regranul', 0):.0f} regranül, toplam {candidate.total_micron:.0f} mikron"
        ),
        "reasons": [{"tier": v.tier, "text": v.reason_text} for v in violations],
        "summary_text": build_elimination_summary(reason_texts),
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

    # Faz G.5 — Aşama 5'te bu ambalaj talebi için zaten kurulmuş firma
    # hafızası kanıtını (Faz G.4) yeniden kullan; kaskadı burada TEKRAR
    # ÇALIŞTIRMAZ, Aşama 5'in seed reçetesinin `reference_search_evidence`
    # alanını okur (o reçete zaten bu talep için en yeni/en kesin kanıtı
    # taşıyor). Hiç Aşama-5 reçetesi yoksa (ör. testler) None kalır.
    seed_recipe = (
        db.query(Recipe)
        .filter_by(packaging_request_id=packaging_request.id)
        .order_by(Recipe.created_at)
        .first()
    )
    reference_evidence = seed_recipe.reference_search_evidence if seed_recipe is not None else None

    line_spec = _line_to_spec(line)
    candidates = generate_candidates(
        line_spec, layer_options, ratio_step_pct=ratio_step_pct,
        target_total_micron=packaging_request.target_thickness_micron,
    )
    generation_breakdown = describe_candidate_generation(line_spec, layer_options, ratio_step_pct=ratio_step_pct)

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
            "generation_breakdown": generation_breakdown,
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
            reference_evidence,
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
        "generation_breakdown": generation_breakdown,
    }
