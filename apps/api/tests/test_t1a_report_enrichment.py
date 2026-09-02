"""Faz T.1a (Madde 31) — §5/§7 zenginleştirmesi: Optimizasyon Hunisi'nin
eleme kategorisi kırılımı (Faz M.2/Q.2b, zaten hesaplı ama rapor hiç
okumuyordu), Açıklanabilir AI'nin (Faz P.3) artık PDF'e render edilmesi,
ve Üretilebilirlik/Altyapı (Faz K.4) hat uygunluk gerekçesinin taşınması.
Hiçbiri yeniden hesaplanmaz -- hepsi REUSE."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.enums import RecipeSource
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.optimization import OptimizationCandidate, OptimizationRun
from app.models.production import SustainabilityResult
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.report_service import build_optimization_report_data


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _material(db):
    polymer = db.query(Polymer).filter_by(code="PE").one_or_none()
    if polymer is None:
        polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
        db.add(polymer)
        db.flush()
    m = Material(
        polymer_id=polymer.id, name="Test Malzeme", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(m)
    db.flush()
    return m


def _line(db):
    line = ProductionLine(
        name="Test Hat", layer_structure="A", layer_count=1, min_micron=10.0, max_micron=1000.0,
        supported_packaging_types=[],
    )
    db.add(line)
    db.flush()
    return line


def _recipe(db, material, line=None, source="sistem_uretti"):
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, line_id=line.id if line else None, source=source,
        status="dogrulandi", is_verified=True, total_micron=70.0,
    )
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0))
    db.add(SustainabilityResult(recipe_id=recipe.id, per_1000_units={"virgin_kg": 10.0, "pcr_kg": 0.0, "regranul_kg": 0.0, "karbon_kg_co2": 18.0, "fire_kg": 1.0, "enerji_kwh": 5.0}, is_actual=True))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_elimination_category_counts_flow_into_report(db_session):
    material = _material(db_session)
    recipe = _recipe(db_session, material, source=RecipeSource.URETILDI.value)

    run = OptimizationRun(
        packaging_request_id=recipe.packaging_request_id,
        parameters={
            "ratio_step_pct": 10, "candidate_count_generated": 50, "survived_constraint_engine_count": 10,
            "elimination_category_counts": {"malzeme_uyumsuzlugu": 12, "mevzuat": 3, "makine_hat_kisiti": 5, "gecmis_basarisizlik": 2, "diger": 0},
        },
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(OptimizationCandidate(run_id=run.id, recipe_id=recipe.id, score=0.9, rank=1, is_finalist=True, score_breakdown={}, decision_basis={}))
    db_session.commit()

    data = build_optimization_report_data(db_session, recipe.id)

    counts = data["optimizasyon_sureci"]["elimination_category_counts"]
    assert counts["gecmis_basarisizlik"] == 2
    assert counts["malzeme_uyumsuzlugu"] == 12


def test_elimination_category_counts_honestly_none_when_absent(db_session):
    material = _material(db_session)
    recipe = _recipe(db_session, material, source=RecipeSource.URETILDI.value)

    run = OptimizationRun(packaging_request_id=recipe.packaging_request_id, parameters={})
    db_session.add(run)
    db_session.flush()
    db_session.add(OptimizationCandidate(run_id=run.id, recipe_id=recipe.id, score=0.9, rank=1, is_finalist=True, score_breakdown={}, decision_basis={}))
    db_session.commit()

    data = build_optimization_report_data(db_session, recipe.id)
    assert data["optimizasyon_sureci"]["elimination_category_counts"] is None


def test_line_match_reason_present_when_line_assigned(db_session):
    material = _material(db_session)
    line = _line(db_session)
    recipe = _recipe(db_session, material, line=line)

    data = build_optimization_report_data(db_session, recipe.id)

    assert "line_match_reason" in data["secilen_recete"]


def test_line_match_reason_none_without_line(db_session):
    material = _material(db_session)
    recipe = _recipe(db_session, material, line=None)

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["secilen_recete"]["line_match_reason"] is None


def test_aciklama_maddeleri_still_present_in_data(db_session):
    """Faz P.3 verisi zaten hesaplıydı -- T.1a sadece PDF render'ını ekledi,
    veri katmanını bozmadı."""
    material = _material(db_session)
    recipe = _recipe(db_session, material, source=RecipeSource.URETILDI.value)
    run = OptimizationRun(packaging_request_id=recipe.packaging_request_id, parameters={})
    db_session.add(run)
    db_session.flush()
    db_session.add(OptimizationCandidate(run_id=run.id, recipe_id=recipe.id, score=0.9, rank=1, is_finalist=True, score_breakdown={"teknik_performans": 0.9}, decision_basis={}))
    db_session.commit()

    data = build_optimization_report_data(db_session, recipe.id)
    assert "aciklama_maddeleri" in data["secilen_recete"]


def test_http_pdf_report_still_renders_after_enrichment(client, db_session):
    material = _material(db_session)
    line = _line(db_session)
    recipe = _recipe(db_session, material, line=line, source=RecipeSource.URETILDI.value)
    run = OptimizationRun(
        packaging_request_id=recipe.packaging_request_id,
        parameters={"elimination_category_counts": {"malzeme_uyumsuzlugu": 4, "mevzuat": 0, "makine_hat_kisiti": 0, "gecmis_basarisizlik": 1, "diger": 0}},
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(OptimizationCandidate(run_id=run.id, recipe_id=recipe.id, score=0.9, rank=1, is_finalist=True, score_breakdown={}, decision_basis={}))
    db_session.commit()

    resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/optimization-report")
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"
