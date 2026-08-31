"""Faz E.4 — Ürün Portföyü: PUT /product-skus/{id} ve GET /product-skus/{id}/detail.
Detay uç noktası Faz B.9'un `build_recipe_traceability`'sini yeniden kullanır
-- izlenebilirlik mantığı burada tekrar kurulmaz, sadece `current_recipe_id`
varsa çağrılır."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.knowledge import Material, Polymer
from app.models.product_sku import ProductSku
from app.models.production import PhysicalTest
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


def _material(db):
    polymer = Polymer(code="PP", name="Polipropilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    m = Material(
        polymer_id=polymer.id, name="PP Virgin Portfoy Test", material_type="virgin", density_g_cm3=0.905,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=38.0, carbon_factor_kg_co2_per_kg=1.9,
    )
    db.add(m)
    db.flush()
    return m


def _verified_recipe_with_passing_test(db, material):
    req = PackagingRequest(
        packaging_type="plastik tabak", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, source="sistem_uretti",
        status="dogrulandi", total_micron=600.0, is_verified=True,
    )
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=600.0))
    db.add(
        PhysicalTest(
            recipe_id=recipe.id, test_type="kalinlik", value=600.0, unit="mikron",
            target_min=540.0, target_max=660.0, result="basarili", passed=True,
        )
    )
    db.commit()
    db.refresh(recipe)
    return recipe


def test_create_sku_with_customer_sector(client):
    resp = client.post(
        "/api/v1/product-skus",
        json={
            "sku_code": "TBK-E4-1", "product_name": "Tabak E4", "packaging_type": "plastik tabak",
            "usage_area": "yemek servisi", "customer_sector": "gida", "target_market": "AB",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["customer_sector"] == "gida"


def test_update_sku_partial(client):
    create_resp = client.post(
        "/api/v1/product-skus",
        json={
            "sku_code": "TBK-E4-2", "product_name": "Tabak E4-2", "packaging_type": "plastik tabak",
            "usage_area": "yemek servisi", "target_market": "AB",
        },
    )
    sku_id = create_resp.json()["id"]

    resp = client.put(f"/api/v1/product-skus/{sku_id}", json={"customer_sector": "kozmetik"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_sector"] == "kozmetik"
    assert body["product_name"] == "Tabak E4-2"  # dokunulmayan alan korunuyor


def test_update_sku_duplicate_code_rejected(client):
    client.post(
        "/api/v1/product-skus",
        json={"sku_code": "TBK-E4-3A", "product_name": "A", "packaging_type": "x", "usage_area": "x", "target_market": "AB"},
    )
    resp_b = client.post(
        "/api/v1/product-skus",
        json={"sku_code": "TBK-E4-3B", "product_name": "B", "packaging_type": "x", "usage_area": "x", "target_market": "AB"},
    )
    sku_b_id = resp_b.json()["id"]

    resp = client.put(f"/api/v1/product-skus/{sku_b_id}", json={"sku_code": "TBK-E4-3A"})
    assert resp.status_code == 400


def test_update_unknown_sku_404(client):
    resp = client.put("/api/v1/product-skus/does-not-exist", json={"customer_sector": "x"})
    assert resp.status_code == 404


def test_sku_detail_traceability_null_without_current_recipe(client):
    create_resp = client.post(
        "/api/v1/product-skus",
        json={
            "sku_code": "TBK-E4-4", "product_name": "Tabak E4-4", "packaging_type": "plastik tabak",
            "usage_area": "yemek servisi", "target_market": "AB",
        },
    )
    sku_id = create_resp.json()["id"]

    resp = client.get(f"/api/v1/product-skus/{sku_id}/detail")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sku_code"] == "TBK-E4-4"
    assert body["traceability"] is None


def test_sku_detail_traceability_populated_when_current_recipe_set(client, db_session):
    material = _material(db_session)
    recipe = _verified_recipe_with_passing_test(db_session, material)

    sku = ProductSku(
        sku_code="TBK-E4-5", product_name="Tabak E4-5", packaging_type="plastik tabak",
        usage_area="yemek servisi", target_market="AB", current_recipe_id=recipe.id,
    )
    db_session.add(sku)
    db_session.commit()
    db_session.refresh(sku)

    resp = client.get(f"/api/v1/product-skus/{sku.id}/detail")
    assert resp.status_code == 200
    body = resp.json()
    assert body["traceability"] is not None
    assert body["traceability"]["recipe_id"] == recipe.id
    assert body["traceability"]["recipe"]["is_verified"] is True
    assert len(body["traceability"]["layers"]) == 1
    assert body["traceability"]["layers"][0]["material"]["name"] == "PP Virgin Portfoy Test"
    assert len(body["traceability"]["physical_tests"]) == 1
    assert body["traceability"]["physical_tests"][0]["result"] == "basarili"


def test_sku_detail_unknown_sku_404(client):
    resp = client.get("/api/v1/product-skus/does-not-exist/detail")
    assert resp.status_code == 404
