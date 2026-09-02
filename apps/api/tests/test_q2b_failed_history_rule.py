"""Faz Q.2 (Madde 25) — Başarısız Reçetelerden Öğrenme. Geçmişte AYNI hatta
denenip fiziksel testi GERÇEKTEN başarısız olmuş bir kombinasyona (aynı
hammadde kümesi + yakın kalınlık) çok yakın yeni bir aday, kısıt
motorundan otomatik elenir; FARKLI bir kombinasyon ETKİLENMEZ (yanlış
pozitif yok)."""
import pytest

from app.constraint_engine.rules import rule_similar_to_failed_history
from app.constraint_engine.types import (
    EvaluationContext,
    EvaluationTier,
    EvaluationVerdict,
    FailedRecipeSignature,
    LayerCandidate,
    LineSpec,
    MaterialSpec,
    PackagingContext,
    RecipeCandidate,
)
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.production import PhysicalTest, ProductionOrder
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services import optimization_service
from app.services.learning_memory_service import build_failed_recipe_signatures


def _material_spec(id_="mat-1", material_type="virgin"):
    return MaterialSpec(
        id=id_, name="Test", polymer_code="PE", material_type=material_type,
        food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        degradation_factor=0.0, mfi_g_10min=None, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )


def _ctx(failed_sigs):
    return EvaluationContext(
        packaging=PackagingContext(packaging_type="plastik_tabak", food_contact=True, target_volume_units=1000),
        line=LineSpec(
            id="line-1", name="Hat-1", layer_structure="A", layer_count=1, min_micron=10, max_micron=200,
            min_gsm=None, max_gsm=None, supported_packaging_types=[], material_max_ratio={},
        ),
        regulations=[],
        failed_recipe_signatures=failed_sigs,
    )


def _candidate(material_id="mat-1", thickness=70.0):
    return RecipeCandidate(
        layers=[LayerCandidate(layer_index=0, layer_label="A", material=_material_spec(material_id), ratio_pct=100.0, thickness_micron=thickness)]
    )


# --- rule_similar_to_failed_history: saf birim testleri --------------------

def test_no_signatures_means_no_elimination():
    assert rule_similar_to_failed_history(_candidate(), _ctx([])) is None


def test_matching_material_and_close_thickness_is_eliminated():
    sig = FailedRecipeSignature(recipe_id="rid12345", version=1, material_ids=frozenset({"mat-1"}), total_micron=70.0, basarisizlik_nedeni="Fiziksel test başarısız — kalinlik: 40.0 mikron.")
    result = rule_similar_to_failed_history(_candidate(thickness=72.0), _ctx([sig]))
    assert result is not None
    assert result.tier == EvaluationTier.TAHMINI_FIZIKSEL_PERFORMANS
    assert result.verdict == EvaluationVerdict.ELENDI
    assert result.reason_code == "gecmis_basarisizlik"
    assert "rid12345"[:8] in result.reason_text
    assert "Fiziksel test başarısız" in result.reason_text


def test_different_material_is_not_eliminated():
    sig = FailedRecipeSignature(recipe_id="rid1", version=1, material_ids=frozenset({"mat-1"}), total_micron=70.0, basarisizlik_nedeni="test")
    result = rule_similar_to_failed_history(_candidate(material_id="mat-2", thickness=70.0), _ctx([sig]))
    assert result is None


def test_thickness_outside_tolerance_is_not_eliminated():
    sig = FailedRecipeSignature(recipe_id="rid1", version=1, material_ids=frozenset({"mat-1"}), total_micron=70.0, basarisizlik_nedeni="test")
    result = rule_similar_to_failed_history(_candidate(thickness=90.0), _ctx([sig]))  # %28 sapma, tolerans %5
    assert result is None


# --- build_failed_recipe_signatures: gerçek DB ------------------------------

def _polymer(db, code="PE"):
    p = db.query(Polymer).filter_by(code=code).one_or_none()
    if p is None:
        p = Polymer(code=code, name=code, category="poliolefin", base_properties={})
        db.add(p)
        db.flush()
    return p


def _material(db, name="Test Malzeme"):
    polymer = _polymer(db)
    m = Material(polymer_id=polymer.id, name=name, material_type="virgin", food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8)
    db.add(m)
    db.flush()
    return m


def _line(db):
    line = ProductionLine(
        name="Hat-1", layer_structure="A", layer_count=1, min_micron=10.0, max_micron=200.0,
        supported_packaging_types=["plastik_tabak"],
    )
    db.add(line)
    db.flush()
    return line


def _failed_recipe(db, line, material, packaging_type="plastik tabak", total_micron=70.0):
    req = PackagingRequest(packaging_type=packaging_type, usage_area="t", product="t", target_market="AB", food_contact=True, target_volume_units=1000, dimensions={})
    db.add(req)
    db.flush()
    recipe = Recipe(packaging_request_id=req.id, version=1, line_id=line.id, source="sistem_uretti", status="revizyon_gerekli", total_micron=total_micron)
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=total_micron))
    db.add(PhysicalTest(recipe_id=recipe.id, test_type="kalinlik", value=40.0, unit="mikron", target_min=63.0, target_max=77.0, result="basarisiz"))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_build_signatures_finds_real_failed_recipe(db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _failed_recipe(db_session, line, material)

    sigs = build_failed_recipe_signatures(db_session, "plastik_tabak", line.id)

    assert len(sigs) == 1
    assert sigs[0].recipe_id == recipe.id
    assert sigs[0].material_ids == frozenset({material.id})
    assert sigs[0].total_micron == 70.0
    assert "kalinlik" in sigs[0].basarisizlik_nedeni


def test_build_signatures_excludes_different_line(db_session):
    line = _line(db_session)
    other_line = _line(db_session)
    material = _material(db_session)
    _failed_recipe(db_session, line, material)

    sigs = build_failed_recipe_signatures(db_session, "plastik_tabak", other_line.id)
    assert sigs == []


def test_build_signatures_excludes_different_packaging_category(db_session):
    line = _line(db_session)
    material = _material(db_session)
    _failed_recipe(db_session, line, material, packaging_type="sise")

    sigs = build_failed_recipe_signatures(db_session, "plastik_tabak", line.id)
    assert sigs == []


def test_build_signatures_excludes_verified_recipe(db_session):
    """Sadece GERÇEKTEN başarısız (status=revizyon_gerekli) reçeteler."""
    line = _line(db_session)
    material = _material(db_session)
    req = PackagingRequest(packaging_type="plastik tabak", usage_area="t", product="t", target_market="AB", food_contact=True, target_volume_units=1000, dimensions={})
    db_session.add(req)
    db_session.flush()
    verified = Recipe(packaging_request_id=req.id, version=1, line_id=line.id, source="sistem_uretti", status="dogrulandi", is_verified=True, total_micron=70.0)
    db_session.add(verified)
    db_session.flush()
    db_session.add(RecipeLayer(recipe_id=verified.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0))
    db_session.commit()

    sigs = build_failed_recipe_signatures(db_session, "plastik_tabak", line.id)
    assert sigs == []


# --- Uçtan uca: run_optimization() gerçekten eler ---------------------------

def test_run_optimization_eliminates_candidate_matching_past_failure(db_session):
    line = _line(db_session)
    material = _material(db_session)
    _failed_recipe(db_session, line, material, packaging_type="plastik tabak", total_micron=70.0)

    req = PackagingRequest(
        packaging_type="plastik tabak", usage_area="t", product="t", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={}, target_thickness_micron=70.0,
    )
    db_session.add(req)
    db_session.flush()
    db_session.add(LineMaterialCompatibility(line_id=line.id, material_id=material.id, max_ratio_pct=100.0))
    db_session.commit()
    db_session.refresh(req)

    result = optimization_service.run_optimization(db_session, req.id, line.id, ratio_step_pct=10)

    assert result["elimination_category_counts"]["gecmis_basarisizlik"] >= 1
    assert result["survived_constraint_engine_count"] == 0


def test_run_optimization_does_not_eliminate_different_thickness(db_session):
    """Aynı hammadde ama farklı hedef kalınlık (%5 toleransın dışında) --
    yanlış pozitif olmamalı, aday hayatta kalmalı."""
    line = _line(db_session)
    material = _material(db_session)
    _failed_recipe(db_session, line, material, packaging_type="plastik tabak", total_micron=70.0)

    req = PackagingRequest(
        packaging_type="plastik tabak", usage_area="t", product="t", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={}, target_thickness_micron=150.0,
    )
    db_session.add(req)
    db_session.flush()
    db_session.add(LineMaterialCompatibility(line_id=line.id, material_id=material.id, max_ratio_pct=100.0))
    db_session.commit()
    db_session.refresh(req)

    result = optimization_service.run_optimization(db_session, req.id, line.id, ratio_step_pct=10)

    assert result["elimination_category_counts"]["gecmis_basarisizlik"] == 0
    assert result["survived_constraint_engine_count"] >= 1
