"""Kısıt motoru: bir aday reçeteyi tüm kurallardan geçirir. Kısayoldan çıkmaz
(short-circuit yapmaz) — "Neden Elendi?" ekranında tüm gerekçeler birlikte
gösterilebilsin diye ilgili tüm ihlalleri toplar."""
from dataclasses import dataclass

from app.constraint_engine.rules import ALL_RULES
from app.constraint_engine.types import (
    EvaluationContext,
    EvaluationResult,
    EvaluationVerdict,
    RecipeCandidate,
)


@dataclass(frozen=True)
class ConstraintCheckResult:
    passed: bool
    violations: list[EvaluationResult]

    @property
    def eliminated(self) -> bool:
        return not self.passed


def evaluate_candidate(
    candidate: RecipeCandidate, ctx: EvaluationContext
) -> ConstraintCheckResult:
    violations: list[EvaluationResult] = []
    for rule in ALL_RULES:
        result = rule(candidate, ctx)
        if result is not None:
            violations.append(result)
    return ConstraintCheckResult(passed=len(violations) == 0, violations=violations)


def filter_candidates(
    candidates: list[RecipeCandidate], ctx: EvaluationContext
) -> tuple[list[RecipeCandidate], list[tuple[RecipeCandidate, list[EvaluationResult]]]]:
    """Döner: (kısıt motorundan geçen adaylar, elenen adaylar + gerekçeleri)."""
    survivors: list[RecipeCandidate] = []
    eliminated: list[tuple[RecipeCandidate, list[EvaluationResult]]] = []
    for candidate in candidates:
        check = evaluate_candidate(candidate, ctx)
        if check.passed:
            survivors.append(candidate)
        else:
            eliminated.append((candidate, check.violations))
    return survivors, eliminated
