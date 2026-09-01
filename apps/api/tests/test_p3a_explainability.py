"""Faz P.3 (Madde 22) — "Neden Bu Reçeteyi Seçtin?" Açıklanabilir AI. Her
madde GERÇEK bir hesaplanmış değere bağlı olmalı; referans yokken bir
azaltım maddesi ASLA üretilmemeli (Faz A kuralı)."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer, Regulation
from app.models.optimization import OptimizationCandidate, OptimizationRun
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer, RecipeMetric
from app.services.explainability_service import build_finalist_explanation_bullets


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _polymer(db, code="PE"):
    p = db.query(Polymer).filter_by(code=code).one_or_none()
    if p is None:
        p = Polymer(code=code, name=code, category="poliolefin", base_properties={})
        db.add(p)
        db.flush()
    return p


def _material(db, material_type="virgin", cost_per_kg=30.0, carbon=1.8, name=None):
    polymer = _polymer(db)
    m = Material(
        polymer_id=polymer.id, name=name or f"Test {material_type}", material_type=material_type,
        food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=cost_per_kg, carbon_factor_kg_co2_per_kg=carbon,
    )
    db.add(m)
    db.flush()
    return m


def _line(db):
    line = ProductionLine(name="Hat-1", layer_structure="A", layer_count=1, min_micron=20.0, max_micron=100.0)
    db.add(line)
    db.flush()
    return line


def _recipe(db, line, material, version=1, source="sistem_uretti", is_verified=True):
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=version, line_id=line.id, source=source,
        status="dogrulandi", is_verified=is_verified, total_micron=70.0,
    )
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0))
    db.commit()
    db.refresh(recipe)
    return recipe


def _add_metrics(db, recipe, virgin_pct=70.0, pcr_pct=30.0, cost=25.0, carbon=1.2):
    for metric_type, value, unit in [
        ("virgin_kullanimi", virgin_pct, "%"), ("pcr_kullanimi", pcr_pct, "%"),
        ("regranul_kullanimi", 0.0, "%"), ("karbon", carbon, "kg_co2/kg"), ("maliyet", cost, "TL/kg"),
    ]:
        db.add(RecipeMetric(recipe_id=recipe.id, metric_type=metric_type, value=value, unit=unit, is_estimated=True, data_source_type="hesaplanan"))
    db.commit()


def _candidate(db, recipe, decision_basis=None, score_breakdown=None):
    run = OptimizationRun(packaging_request_id=recipe.packaging_request_id, parameters={})
    db.add(run)
    db.flush()
    candidate = OptimizationCandidate(
        run_id=run.id, recipe_id=recipe.id, score=0.8, rank=1, is_finalist=True,
        score_breakdown=score_breakdown or {}, decision_basis=decision_basis or {},
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def test_no_reference_means_no_reduction_bullet(db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)
    _add_metrics(db_session, recipe)
    candidate = _candidate(
        db_session, recipe,
        decision_basis={"hat_parametreleri": {"hat": "Hat-1"}, "mevzuat_maddeleri": []},
        score_breakdown={"karbon": 0.5, "maliyet": 0.5},
    )

    bullets = build_finalist_explanation_bullets(db_session, candidate)

    assert not any("azaltıyor" in b for b in bullets), "Referans yokken azaltım iddiası uydurulmamalı"
    assert any("Hat-1" in b for b in bullets)


def test_reference_present_produces_real_virgin_reduction_bullet(db_session):
    line = _line(db_session)
    material = _material(db_session)

    ref_recipe = _recipe(db_session, line, material, version=1)
    _add_metrics(db_session, ref_recipe, virgin_pct=100.0, pcr_pct=0.0)
    ref_recipe.is_verified = True
    db_session.commit()

    new_recipe = _recipe(db_session, line, material, version=2)
    _add_metrics(db_session, new_recipe, virgin_pct=70.0, pcr_pct=30.0)
    candidate = _candidate(db_session, new_recipe, decision_basis={}, score_breakdown={})

    bullets = build_finalist_explanation_bullets(db_session, candidate)

    assert any("Virgin tüketimini %30 azaltıyor." == b for b in bullets)


def test_carbon_and_cost_bullets_reflect_real_scores(db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)
    _add_metrics(db_session, recipe)
    candidate = _candidate(db_session, recipe, score_breakdown={"karbon": 0.8, "maliyet": 0.2})

    bullets = build_finalist_explanation_bullets(db_session, candidate)

    assert any("Karbon etkisi virgin bazlı referansa göre daha düşük." == b for b in bullets)
    assert any("Maliyet artışı belirgin ölçüde yüksek." == b for b in bullets)


def test_regulatory_target_bullet_uses_real_threshold(db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)
    _add_metrics(db_session, recipe, pcr_pct=30.0, virgin_pct=70.0)
    reg = Regulation(
        code="PPWR-ART-7", title="Geri Dönüştürülmüş İçerik", category="geri_donusturulmus_icerik", description="t",
        criteria={"targets": [{"food_contact": True, "pet": False, "by_year": {"2030": 10.0}}]},
    )
    db_session.add(reg)
    db_session.commit()
    candidate = _candidate(db_session, recipe)

    bullets = build_finalist_explanation_bullets(db_session, candidate)

    assert any("hedefini karşılıyor" in b for b in bullets)


def test_http_optimization_run_includes_explanation_bullets(client, db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)
    _add_metrics(db_session, recipe)
    candidate = _candidate(db_session, recipe, decision_basis={"hat_parametreleri": {"hat": "Hat-1"}, "mevzuat_maddeleri": []})

    resp = client.get(f"/api/v1/optimization/runs/{candidate.run_id}")
    assert resp.status_code == 200, resp.text
    finalist = resp.json()["finalists"][0]
    assert any("Hat-1" in b for b in finalist["explanation_bullets"])


def test_http_finalize_includes_bullets_and_eliminated(client, db_session):
    from app.models.production import PhysicalTest

    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)
    _add_metrics(db_session, recipe)
    run = OptimizationRun(
        packaging_request_id=recipe.packaging_request_id, parameters={},
        notable_eliminated=[{"composition_summary": "test", "reasons": [], "summary_text": "elendi"}],
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(
        OptimizationCandidate(
            run_id=run.id, recipe_id=recipe.id, score=0.8, rank=1, is_finalist=True,
            score_breakdown={}, decision_basis={"hat_parametreleri": {"hat": "Hat-1"}, "mevzuat_maddeleri": []},
        )
    )
    db_session.add(PhysicalTest(recipe_id=recipe.id, test_type="kalinlik", value=70.0, unit="mikron", result="basarili"))
    db_session.commit()

    resp = client.post(f"/api/v1/production-flow/recipes/{recipe.id}/finalize")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert any("Hat-1" in b for b in body["aciklama_maddeleri"])
    assert len(body["notable_eliminated"]) == 1
