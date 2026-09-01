from pydantic import BaseModel, ConfigDict

from app.schemas.recipe import RecipeOut


class OptimizationCandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    recipe_id: str
    score: float
    rank: int
    is_finalist: bool
    score_breakdown: dict
    carbon_data_quality: str = "tanimlanmadi"
    justification_text: str | None = None
    decision_basis: dict
    recipe: RecipeOut
    # Faz P.3 (Madde 22) — additive. ORM'de bir kolon DEĞİL, router'da
    # `explainability_service.build_finalist_explanation_bullets()` ile
    # doldurulur (bkz. app/api/v1/routers/optimization.py).
    explanation_bullets: list[str] = []


class EliminationReasonOut(BaseModel):
    """Faz J.0 — her eleme gerekçesinin GERÇEK `EvaluationTier`'ı
    (kesin_teknik_kisit/malzeme_proses_kisiti, bkz. app/constraint_engine/
    types.py) burada korunur; önceden sadece düz metin taşınıyordu."""

    tier: str
    text: str


class EliminatedCandidateOut(BaseModel):
    """Elenen bir aday — reçetenin tam kaydı yok (DB'ye yazılmaz), sadece
    kompozisyon özeti + gerekçeler gösterilir ('Neden Elendi?')."""

    composition_summary: str
    reasons: list[EliminationReasonOut]
    summary_text: str


class ZeroFinalistDiagnosisOut(BaseModel):
    """Faz M.3 (Madde 13) — 0 finalist teşhis ekranı (bkz. optimization_
    service._diagnose_zero_finalists). SADECE finalists boşken dolu."""

    dominant_reason_code: str | None
    dominant_reason_text: str | None
    affected_pct: int | None
    alternative_line_name: str | None
    alternative_line_score_pct: int | None
    suggestion_text: str


class GenerationBreakdownLayerOut(BaseModel):
    layer_label: str
    virgin_material_name: str
    recycled_material_names: list[str]
    variant_count: int


class GenerationBreakdownOut(BaseModel):
    """Faz D.1 — 'Adaylar Nasıl Oluşturuldu?'. `total`, `optimization_
    service.run_optimization`'ın gerçekten ürettiği `generated_candidate_
    count` ile HER ZAMAN birebir eşittir (aynı hesaplamadan türetilir,
    bkz. app/optimization/candidate_generator.py describe_candidate_
    generation)."""

    layers: list[GenerationBreakdownLayerOut]
    total: int
    formula_text: str


class OptimizationRunOut(BaseModel):
    id: str
    packaging_request_id: str
    finalists: list[OptimizationCandidateOut]
    notable_eliminated: list[EliminatedCandidateOut]
    generated_candidate_count: int
    survived_constraint_engine_count: int
    generation_breakdown: GenerationBreakdownOut | None = None
    # Faz M.2 (Madde 12) — TÜM elenenlerin kategorik dağılımı (huni
    # görselleştirmesinin yanındaki özet). Anahtarlar: malzeme_uyumsuzlugu,
    # mevzuat, makine_hat_kisiti, diger.
    elimination_category_counts: dict[str, int] = {}
    # Faz M.3 (Madde 13) — SADECE finalists boşken dolu (bkz.
    # optimization_service._diagnose_zero_finalists).
    diagnosis: ZeroFinalistDiagnosisOut | None = None
