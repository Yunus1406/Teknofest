"""Faz C.2 — Dijital Ürün Pasaportu içerik derleme + public/authorized
erişim ayrımı. `build_passport_content` doğrudan (servis seviyesi) test
edilir; paylaşılan-anahtar KAPISI (`?authorized_key=...`) router seviyesinde
olduğundan o kısım TestClient ile test edilir (bkz. test_production_order_
handoff.py'deki aynı `client` fixture deseni)."""
import base64

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.knowledge import Material, Polymer
from app.models.production import PhysicalTest
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.passport_service import build_passport_content, get_or_create_passport


def _material(db):
    polymer = Polymer(code="PP", name="Polipropilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    material = Material(
        polymer_id=polymer.id, name="PP Virgin Test", material_type="virgin",
        manufacturer="Test Petrokimya", supplier="Test Tedarik A.Ş.", lot_number="LOT-2026-01",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=32.0,
        carbon_factor_kg_co2_per_kg=1.9,
    )
    db.add(material)
    db.flush()
    return material


def _verified_recipe_with_layer(db):
    material = _material(db)
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, source="sistem_uretti", status="dogrulandi",
        is_verified=True, total_micron=70.0,
    )
    db.add(recipe)
    db.flush()
    db.add(
        RecipeLayer(
            recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id,
            ratio_pct=100.0, thickness_micron=70.0,
        )
    )
    db.commit()
    db.refresh(recipe)
    return recipe


# --- Servis seviyesi: içerik derleme ---------------------------------------

def test_public_content_never_carries_authorized_key(db_session):
    recipe = _verified_recipe_with_layer(db_session)
    passport = get_or_create_passport(db_session, recipe.id)

    content = build_passport_content(db_session, passport, include_authorized=False)

    assert content["authorized"] is None
    assert "layer_materials" not in content["public"]
    assert content["public"]["header"]["passport_no"] == passport.passport_no


def test_authorized_content_includes_commercial_layer_detail(db_session):
    recipe = _verified_recipe_with_layer(db_session)
    passport = get_or_create_passport(db_session, recipe.id)

    content = build_passport_content(db_session, passport, include_authorized=True)

    assert content["authorized"] is not None
    layer_materials = content["authorized"]["layer_materials"]
    assert len(layer_materials) == 1
    assert layer_materials[0]["manufacturer"] == "Test Petrokimya"
    assert layer_materials[0]["supplier"] == "Test Tedarik A.Ş."
    assert layer_materials[0]["lot_number"] == "LOT-2026-01"
    assert content["authorized"]["traceability"]["recipe_id"] == recipe.id


def test_qr_code_is_a_valid_png_data_uri(db_session):
    recipe = _verified_recipe_with_layer(db_session)
    passport = get_or_create_passport(db_session, recipe.id)

    content = build_passport_content(db_session, passport, include_authorized=False)

    data_uri = content["qr_code_data_uri"]
    assert data_uri.startswith("data:image/png;base64,")
    raw = base64.b64decode(data_uri.split(",", 1)[1])
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


def test_no_reference_means_no_fabricated_gains(db_session):
    """Faz A kuralı: karşılaştırma temeli (doğrulanmış aynı türde başka bir
    reçete) yoksa iyileşme yüzdesi ASLA uydurulmaz."""
    recipe = _verified_recipe_with_layer(db_session)
    passport = get_or_create_passport(db_session, recipe.id)

    content = build_passport_content(db_session, passport, include_authorized=False)

    assert content["public"]["environmental"]["has_reference"] is False
    assert content["public"]["environmental"]["gains_pct"] is None


def test_regulatory_disclaimer_never_claims_legal_certification(db_session):
    recipe = _verified_recipe_with_layer(db_session)
    passport = get_or_create_passport(db_session, recipe.id)

    content = build_passport_content(db_session, passport, include_authorized=False)

    disclaimer = content["public"]["regulatory_disclaimer"]
    assert "sertifikasyon" in disclaimer or "sertifika" in disclaimer
    assert "değildir" in disclaimer  # "...sertifikasyonu değildir" -- reddediyor, iddia etmiyor


def test_physical_performance_is_beklemede_when_no_tests_exist(db_session):
    recipe = _verified_recipe_with_layer(db_session)
    passport = get_or_create_passport(db_session, recipe.id)

    content = build_passport_content(db_session, passport, include_authorized=False)

    assert content["public"]["status_summary"]["physical_performance"] == "Beklemede"


def test_physical_performance_reflects_failed_test(db_session):
    recipe = _verified_recipe_with_layer(db_session)
    db_session.add(
        PhysicalTest(recipe_id=recipe.id, test_type="kalinlik", value=50.0, unit="mikron", passed=False)
    )
    db_session.commit()
    passport = get_or_create_passport(db_session, recipe.id)

    content = build_passport_content(db_session, passport, include_authorized=False)

    assert content["public"]["status_summary"]["physical_performance"] == "Başarısız"


# --- Router seviyesi: paylaşılan-anahtar kapısı ----------------------------

class _FakeSettings:
    dpp_authorized_key = "test-secret-key"
    public_web_base_url = "http://localhost:3000"


@pytest.fixture()
def client(db_session, monkeypatch):
    monkeypatch.setattr("app.api.v1.routers.passport.get_settings", lambda: _FakeSettings())
    monkeypatch.setattr("app.services.passport_service.get_settings", lambda: _FakeSettings())

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_post_passport_never_returns_authorized_data(client, db_session):
    recipe = _verified_recipe_with_layer(db_session)

    resp = client.post("/api/v1/passports", json={"recipe_id": recipe.id})

    assert resp.status_code == 200, resp.text
    assert resp.json()["authorized"] is None


def test_get_passport_without_key_returns_no_authorized_data(client, db_session):
    recipe = _verified_recipe_with_layer(db_session)
    passport = get_or_create_passport(db_session, recipe.id)

    resp = client.get(f"/api/v1/passports/{passport.passport_no}")

    assert resp.status_code == 200
    assert resp.json()["authorized"] is None


def test_get_passport_with_wrong_key_is_silently_denied_not_error(client, db_session):
    recipe = _verified_recipe_with_layer(db_session)
    passport = get_or_create_passport(db_session, recipe.id)

    resp = client.get(f"/api/v1/passports/{passport.passport_no}", params={"authorized_key": "wrong"})

    assert resp.status_code == 200  # 403/401 değil -- sessizce reddedilir
    assert resp.json()["authorized"] is None


def test_get_passport_with_correct_key_returns_authorized_data(client, db_session):
    recipe = _verified_recipe_with_layer(db_session)
    passport = get_or_create_passport(db_session, recipe.id)

    resp = client.get(
        f"/api/v1/passports/{passport.passport_no}",
        params={"authorized_key": "test-secret-key"},
    )

    assert resp.status_code == 200
    assert resp.json()["authorized"] is not None
    assert len(resp.json()["authorized"]["layer_materials"]) == 1


def test_get_unknown_passport_returns_404(client):
    resp = client.get("/api/v1/passports/DPP-2026-999999")
    assert resp.status_code == 404


def test_create_passport_for_unverified_recipe_returns_400(client, db_session):
    material = _material(db_session)
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db_session.add(req)
    db_session.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, source="sistem_uretti",
        status="onerildi", is_verified=False,
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)

    resp = client.post("/api/v1/passports", json={"recipe_id": recipe.id})

    assert resp.status_code == 400
