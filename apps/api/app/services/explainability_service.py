"""Faz P.3 (Madde 22) — "Neden Bu Reçeteyi Seçtin?" Açıklanabilir Yapay
Zeka. Faz G.5'in akıcı `justification_text`'ini (bkz. app/llm/
justification.py) YENİDEN KURMAZ, YANINA madde madde (bullet) bir liste
ekler -- her madde GERÇEK, zaten hesaplanmış bir değere (comparison,
decision_basis, score_breakdown) bağlıdır; veri yoksa o madde ATLANIR,
jenerik doldurma metni YAZILMAZ. "Neden diğerleri seçilmedi?" için ayrı bir
hesap gerekmez -- `OptimizationRun.notable_eliminated` (Faz C.4/M.1) zaten
somut, sayısal gerekçe metinleri taşır."""
from sqlalchemy.orm import Session

from app.constraint_engine.types import RegulationSpec
from app.models.knowledge import Regulation
from app.models.optimization import OptimizationCandidate
from app.services import production_flow_service
from app.services.scenario_service import _recipe_to_candidate, _regulatory_comparison


def _pct_reduction(old: float | None, new: float | None) -> float | None:
    """`report_service._pct_reduction` ile AYNI formül -- döngüsel import'a
    girmemek için burada bilinçli küçük bir kopya (bkz. modül docstring'i,
    aynı disiplin `traceability_service._find_reference_recipe`'de de var)."""
    if old is None or new is None or old == 0:
        return None
    return round(((old - new) / old) * 100, 1)


def build_finalist_explanation_bullets(db: Session, candidate: OptimizationCandidate) -> list[str]:
    recipe = candidate.recipe
    comparison = production_flow_service.build_comparison(db, recipe)
    recommended = comparison["recommended"]
    decision_basis = candidate.decision_basis or {}
    breakdown = candidate.score_breakdown or {}
    bullets: list[str] = []

    if comparison["reference"] is not None:
        virgin_delta = _pct_reduction(comparison["reference"]["virgin_pct"], recommended["virgin_pct"])
        if virgin_delta is not None and virgin_delta > 0:
            bullets.append(f"Virgin tüketimini %{virgin_delta:.0f} azaltıyor.")

    hat = (decision_basis.get("hat_parametreleri") or {}).get("hat")
    if hat:
        bullets.append(f"{hat} hattında üretilebilir.")

    maddeler = decision_basis.get("mevzuat_maddeleri") or []
    if maddeler:
        bullets.append(f"Mevzuat madde(ler)i {', '.join(maddeler)} ön kontrolünden geçti.")

    if recipe.packaging_request is not None:
        rc_candidate = _recipe_to_candidate(recipe)
        regulations = [
            RegulationSpec(
                code=r.code, title=r.title, category=r.category,
                criteria=r.criteria, applicable_packaging_types=r.applicable_packaging_types,
            )
            for r in db.query(Regulation).all()
        ]
        reg_comparison = _regulatory_comparison(
            rc_candidate, regulations, recipe.packaging_request.food_contact, recommended["pcr_pct"]
        )
        if reg_comparison["hedef_pct"] is not None:
            if reg_comparison["hedefi_karsiliyor_mu"]:
                bullets.append(
                    f"PCR/geri dönüştürülmüş içerik hedefini karşılıyor "
                    f"(%{recommended['pcr_pct']:.0f} ≥ %{reg_comparison['hedef_pct']:.0f})."
                )
            else:
                bullets.append(
                    f"PCR/geri dönüştürülmüş içerik hedefinin altında "
                    f"(%{recommended['pcr_pct']:.0f} < %{reg_comparison['hedef_pct']:.0f})."
                )

    karbon_skoru = breakdown.get("karbon")
    if karbon_skoru is not None:
        if karbon_skoru > 0.55:
            bullets.append("Karbon etkisi virgin bazlı referansa göre daha düşük.")
        elif karbon_skoru < 0.45:
            bullets.append("Karbon etkisi virgin bazlı referansa göre daha yüksek.")

    maliyet_skoru = breakdown.get("maliyet")
    if maliyet_skoru is not None:
        if maliyet_skoru >= 0.45:
            bullets.append("Maliyet artışı izin verilen sınırda ya da altında.")
        else:
            bullets.append("Maliyet artışı belirgin ölçüde yüksek.")

    return bullets
