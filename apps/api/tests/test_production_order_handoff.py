"""Aşama 9 (üretim emri oluşturma) -> Aşama 10 (canlı takip) API sözleşmesi.

Regresyon: Aşama 9'da üretim emri oluşturulduktan sonra Aşama 10'a geçildiğinde
"Üretim emri bulunamadı" (404) hatası alınıyordu. Kök neden backend'de değil,
frontend'in case-store'unda idi (yeni bir reçete seçildiğinde eski
productionOrderId temizlenmiyordu) — ama bu test, Aşama 9'un döndürdüğü
`id`'nin Aşama 10'un beklediği `order_id` route parametresiyle birebir aynı
kayda karşılık geldiğini ve var olmayan bir ID için sözleşmenin net bir 404
verdiğini HTTP katmanında sabitler; ileride bu uçlardan biri (route, foreign
key, response şeması) kazayla bozulursa bu test kırılır."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def recipe_id(db_session):
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()
    material = Material(
        polymer_id=polymer.id, name="PE Virgin", material_type="virgin", density_g_cm3=0.92,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    db_session.add(material)
    line = ProductionLine(
        name="Hat-Test", layer_structure="A", layer_count=1, min_micron=10, max_micron=1000,
        supported_packaging_types=["esnek_film_ambalaj"],
    )
    db_session.add(line)
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="t", product="t", target_market="t",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 400, "width_mm": 300},
    )
    db_session.add(req)
    db_session.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, line_id=line.id, source="sistem_uretti",
        status="onerildi", total_micron=70.0,
    )
    db_session.add(recipe)
    db_session.flush()
    db_session.add(
        RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0)
    )
    db_session.add(LineMaterialCompatibility(line_id=line.id, material_id=material.id, max_ratio_pct=100.0))
    db_session.commit()
    return recipe.id


def test_production_order_created_in_stage9_is_reachable_in_stage10(client, recipe_id):
    create_resp = client.post(f"/api/v1/production-flow/recipes/{recipe_id}/production-orders", params={"qty_units": 5000})
    assert create_resp.status_code == 200, create_resp.text
    order = create_resp.json()
    assert order["recipe_id"] == recipe_id  # Aşama 9 özetindeki reçeteyle eşleşmeli

    live_resp = client.post(f"/api/v1/production-flow/production-orders/{order['id']}/simulate-live-data")
    assert live_resp.status_code == 200, live_resp.text
    rows = live_resp.json()
    assert len(rows) > 0


def test_nonexistent_production_order_returns_clean_404(client):
    resp = client.post("/api/v1/production-flow/production-orders/does-not-exist/simulate-live-data")
    assert resp.status_code == 404
    assert "bulunamadı" in resp.json()["detail"].lower()


def test_stale_order_from_a_different_recipe_is_distinguishable(client, recipe_id, db_session):
    """İki farklı reçete için iki ayrı üretim emri oluşturulursa, biri
    diğerinin ID'siyle karıştırılmamalı -- her üretim emri kendi recipe_id'sini
    taşımalı (case-store'un 'farklı reçete seçildiğinde eski üretim emrini
    temizle' mantığının dayandığı sözleşme)."""
    polymer = db_session.query(Polymer).first()
    material2 = Material(
        polymer_id=polymer.id, name="PE Virgin 2", material_type="virgin", density_g_cm3=0.92,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    db_session.add(material2)
    db_session.flush()
    other_recipe = db_session.get(Recipe, recipe_id)
    recipe2 = Recipe(
        packaging_request_id=other_recipe.packaging_request_id, version=2, line_id=other_recipe.line_id,
        source="sistem_uretti", status="onerildi", total_micron=80.0,
    )
    db_session.add(recipe2)
    db_session.flush()
    db_session.add(RecipeLayer(recipe_id=recipe2.id, layer_index=0, layer_label="A", material_id=material2.id, ratio_pct=100.0, thickness_micron=80.0))
    db_session.commit()

    order1 = client.post(f"/api/v1/production-flow/recipes/{recipe_id}/production-orders", params={"qty_units": 1000}).json()
    order2 = client.post(f"/api/v1/production-flow/recipes/{recipe2.id}/production-orders", params={"qty_units": 1000}).json()

    assert order1["id"] != order2["id"]
    assert order1["recipe_id"] == recipe_id
    assert order2["recipe_id"] == recipe2.id
