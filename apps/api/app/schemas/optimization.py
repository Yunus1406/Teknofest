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


class EliminatedCandidateOut(BaseModel):
    """Elenen bir aday — reçetenin tam kaydı yok (DB'ye yazılmaz), sadece
    kompozisyon özeti + gerekçeler gösterilir ('Neden Elendi?')."""

    composition_summary: str
    reasons: list[str]
    summary_text: str


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
