"""Faz F.6 — Mekanik Test Standartları Kütüphanesi. `suggested_min`/
`suggested_max` YENİ, ayrı bir öneri alanıdır -- `target_min`/`target_max`
(gerçek geçme/kalma kriteri) her zaman None kalır (Faz D.2'nin kuralı
DEĞİŞMEDİ, bkz. tests/test_test_targets.py'nin AYNI şekilde geçtiği)."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.knowledge_base.loader import load_all
from app.main import app
from app.models.knowledge import Material, Polymer
from app.models.mechanical_test_standard import MechanicalTestStandard
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.test_targets import suggested_physical_test_targets


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_mechanical_test_standards_loaded_for_all_five_test_types(db_session):
    load_all(db_session)
    rows = db_session.query(MechanicalTestStandard).all()
    test_types = {r.test_type for r in rows}
    assert test_types == {"tensile", "elongation", "dart_impact", "tear", "seal"}


def test_mechanical_test_standard_loader_is_idempotent(db_session):
    load_all(db_session)
    count_first = db_session.query(MechanicalTestStandard).count()
    load_all(db_session)
    count_second = db_session.query(MechanicalTestStandard).count()
    assert count_first == count_second == 5


def test_suggested_targets_without_references_leaves_suggestion_fields_none():
    """Mevcut davranış (referans geçirilmeden çağrılırsa) DEĞİŞMEDİ --
    tests/test_test_targets.py'nin varsayımı budur."""
    from types import SimpleNamespace

    material = SimpleNamespace(density_g_cm3=0.92, material_type="virgin", carbon_factor_kg_co2_per_kg=1.8)
    layer = SimpleNamespace(layer_index=0, material=material, ratio_pct=100.0, thickness_micron=70.0)
    recipe = SimpleNamespace(layers=[layer], total_micron=70.0)

    targets = suggested_physical_test_targets(recipe)
    tensile = next(t for t in targets if t.test_type == "tensile")
    assert tensile.target_min is None
    assert tensile.target_max is None
    assert tensile.suggested_min is None
    assert tensile.suggested_max is None


def test_suggested_targets_with_references_populates_suggestion_but_not_target(db_session):
    """F.6'nın ana sözleşmesi: referans veri geçirildiğinde suggested_min/max
    dolar AMA target_min/max HÂLÂ None kalır -- otomatik bir geçme/kalma
    kriteri asla üretilmez."""
    load_all(db_session)
    mechanical_references = {
        row.test_type: row
        for row in db_session.query(MechanicalTestStandard).filter_by(packaging_category=None).all()
    }

    from types import SimpleNamespace

    material = SimpleNamespace(density_g_cm3=0.92, material_type="virgin", carbon_factor_kg_co2_per_kg=1.8)
    layer = SimpleNamespace(layer_index=0, material=material, ratio_pct=100.0, thickness_micron=70.0)
    recipe = SimpleNamespace(layers=[layer], total_micron=70.0)

    targets = suggested_physical_test_targets(recipe, mechanical_references)
    for t in targets:
        if t.test_type in ("tensile", "elongation", "dart_impact", "tear", "seal"):
            assert t.target_min is None
            assert t.target_max is None
            assert t.nominal_value is None
            assert t.suggested_min is not None
            assert t.suggested_max is not None
            assert t.suggestion_source is not None

    tensile = next(t for t in targets if t.test_type == "tensile")
    assert tensile.suggested_min == 15
    assert tensile.suggested_max == 40
    assert tensile.suggestion_source == "ASTM D882"


def test_suggested_test_targets_endpoint_includes_mechanical_suggestions(client, db_session):
    load_all(db_session)
    polymer = db_session.query(Polymer).filter_by(code="PE").one()
    material = Material(
        polymer_id=polymer.id, name="PE Virgin F6 Test", material_type="virgin", density_g_cm3=0.92,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    db_session.add(material)
    db_session.flush()
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db_session.add(req)
    db_session.flush()
    recipe = Recipe(packaging_request_id=req.id, version=1, source="sistem_uretti", status="onerildi", total_micron=70.0)
    db_session.add(recipe)
    db_session.flush()
    db_session.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0))
    db_session.commit()
    db_session.refresh(recipe)

    resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/suggested-test-targets")
    assert resp.status_code == 200
    body = resp.json()
    tensile = next(t for t in body if t["test_type"] == "tensile")
    assert tensile["target_min"] is None
    assert tensile["target_max"] is None
    assert tensile["suggested_min"] == 15
    assert tensile["suggested_max"] == 40


def test_reference_mechanical_test_standards_endpoint(client, db_session):
    load_all(db_session)
    resp = client.get("/api/v1/reference/mechanical-test-standards")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 5
    assert all(r["is_demo_placeholder"] for r in body)
