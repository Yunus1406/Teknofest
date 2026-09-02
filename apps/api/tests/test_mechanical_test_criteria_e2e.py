"""Mekanik Test Kabul Kriterleri — Aşama 2'de kullanıcının GERÇEKTEN girdiği
kriterin, Aşama 11'in "önerilen test hedefleri" endpoint'ine uçtan uca
aktığını doğrular (route → service → response). Kullanıcı önceden bu hedefi
hiçbir yerde giremiyordu (bkz. app/services/test_targets.py "elle
girilmelidir" notu, hiçbir UI/alan bu notu karşılamıyordu)."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
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


def _material(db):
    polymer = db.query(Polymer).filter_by(code="PE").one_or_none()
    if polymer is None:
        polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
        db.add(polymer)
        db.flush()
    m = Material(
        polymer_id=polymer.id, name="Test Malzeme", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8, density_g_cm3=0.92,
    )
    db.add(m)
    db.flush()
    return m


def _recipe(db, material, mechanical_test_criteria=None):
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
        mechanical_test_criteria=mechanical_test_criteria or {},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(packaging_request_id=req.id, version=1, source="sistem_uretti", status="dogrulandi", is_verified=True, total_micron=70.0)
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_suggested_test_targets_uses_real_user_criteria(client, db_session):
    material = _material(db_session)
    recipe = _recipe(db_session, material, mechanical_test_criteria={"tensile": {"min": 25.0, "max": 40.0}})

    resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/suggested-test-targets")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    tensile = next(t for t in body if t["test_type"] == "tensile")
    assert tensile["target_min"] == 25.0
    assert tensile["target_max"] == 40.0
    assert tensile["target_source"] == "kullanici_girisi"

    elongation = next(t for t in body if t["test_type"] == "elongation")
    assert elongation["target_min"] is None
    assert elongation["target_source"] is None
    assert "elle girilmelidir" in elongation["note"]


def test_suggested_test_targets_without_user_criteria_stays_honest(client, db_session):
    material = _material(db_session)
    recipe = _recipe(db_session, material)

    resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/suggested-test-targets")
    assert resp.status_code == 200

    for t in resp.json():
        if t["test_type"] in ("tensile", "elongation", "dart_impact", "tear", "seal"):
            assert t["target_min"] is None
            assert t["target_source"] is None


def test_full_flow_criteria_entered_then_test_actually_evaluated_against_it(client, db_session):
    """Uçtan uca: Aşama 2'de kriter girilir → Aşama 11 bu kriteri hedef
    olarak sunar → kullanıcı bu hedefe göre test gönderir → gerçek pass/fail
    üretilir (submit_physical_verification submitted target'a göre değerlendirir)."""
    material = _material(db_session)
    recipe = _recipe(db_session, material, mechanical_test_criteria={"tensile": {"min": 20.0, "max": 30.0}})

    from app.models.infrastructure import ProductionLine
    from app.models.production import ProductionOrder

    line = ProductionLine(name="Hat-1", layer_structure="A", layer_count=1, min_micron=10.0, max_micron=200.0)
    db_session.add(line)
    db_session.flush()
    order = ProductionOrder(recipe_id=recipe.id, line_id=line.id, status="tamamlandi", scheduled_qty_units=100)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    targets_resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/suggested-test-targets")
    tensile_target = next(t for t in targets_resp.json() if t["test_type"] == "tensile")
    assert tensile_target["target_min"] == 20.0

    submit_resp = client.post(
        "/api/v1/production-flow/physical-verification",
        json={
            "production_order_id": order.id,
            "tests": [
                {
                    "test_type": "tensile", "value": 25.0, "unit": tensile_target["unit"],
                    "target_min": tensile_target["target_min"], "target_max": tensile_target["target_max"],
                    "test_method": tensile_target["test_method"],
                }
            ],
        },
    )
    assert submit_resp.status_code == 200, submit_resp.text
    result = submit_resp.json()["results"][0]
    assert result["result"] == "basarili"
    assert result["target_min"] == 20.0


def test_real_asama2_flow_create_draft_then_update_with_criteria(client, db_session):
    """Bu, gerçek kullanıcı akışının BİREBİR aynısı: Aşama 2'nin
    `ensureDraftRequest()`'i şartname çıkarımı sırasında BOŞ
    mechanical_test_criteria ile bir taslak POST'lar; kullanıcı mekanik
    kriterleri doldurup "Onaylıyorum"a bastığında ayrı bir PUT ile
    güncellenir. Önceki test (`test_suggested_test_targets_uses_real_user_
    criteria`) reçeteyi/talebi TEK ADIMDA, kriter zaten dolu olarak
    DB session'a yazıyordu -- bu, gerçek çift adımlı HTTP akışını (POST boş
    → PUT dolu) hiç sınamıyordu. Bir canlı dev sunucusunda (kod
    değişikliklerini hiç yeniden yüklememiş, eski bir süreç) bu iki adımlı
    akış sessizce kriterleri kaybediyordu; bu test o senaryoyu kilitler."""
    # 1) Aşama 2 "Alanları Çıkar" anı — boş taslak POST.
    create_resp = client.post(
        "/api/v1/packaging-flow/requests",
        json={
            "packaging_type": "esnek film ambalaj", "usage_area": "test", "product": "test ürün",
            "target_market": "AB", "food_contact": True, "target_volume_units": 1000,
            "dimensions": {}, "mechanical_test_criteria": {},
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    req_id = create_resp.json()["id"]
    assert create_resp.json()["mechanical_test_criteria"] == {}

    # 2) Kullanıcı Mekanik Test Kabul Kriterleri'ni doldurup "Bilgileri
    # Onaylıyorum, Devam Et"e basar -- AYRI bir PUT isteği.
    update_resp = client.put(
        f"/api/v1/packaging-flow/requests/{req_id}",
        json={
            "packaging_type": "esnek film ambalaj", "usage_area": "test", "product": "test ürün",
            "target_market": "AB", "food_contact": True, "target_volume_units": 1000,
            "dimensions": {},
            "mechanical_test_criteria": {
                "tensile": {"min": 25.0, "max": 40.0},
                "seal": {"min": 5.0, "max": None},
            },
        },
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["mechanical_test_criteria"] == {
        "tensile": {"min": 25.0, "max": 40.0},
        "seal": {"min": 5.0, "max": None},
    }

    # 3) Veritabanında GERÇEKTEN kalıcı olduğunu (aynı satır, yeniden okuma
    # ile) doğrula -- response body'nin kendisi değil, DB'nin kendisi.
    get_resp = client.get(f"/api/v1/packaging-flow/requests/{req_id}")
    assert get_resp.json()["mechanical_test_criteria"]["tensile"] == {"min": 25.0, "max": 40.0}

    # 4) Bu talebe bağlı bir reçete için Aşama 11'in hedef önerisi bu
    # kriteri GERÇEKTEN kullanmalı -- tam zincir: POST → PUT → Recipe →
    # suggested-test-targets.
    from app.models.recipe import PackagingRequest, Recipe, RecipeLayer

    req = db_session.get(PackagingRequest, req_id)
    material = _material(db_session)
    recipe = Recipe(packaging_request_id=req.id, version=1, source="sistem_uretti", status="dogrulandi", is_verified=True, total_micron=70.0)
    db_session.add(recipe)
    db_session.flush()
    db_session.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0))
    db_session.commit()
    db_session.refresh(recipe)

    targets_resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/suggested-test-targets")
    assert targets_resp.status_code == 200, targets_resp.text
    tensile = next(t for t in targets_resp.json() if t["test_type"] == "tensile")
    seal = next(t for t in targets_resp.json() if t["test_type"] == "seal")
    assert tensile["target_min"] == 25.0
    assert tensile["target_max"] == 40.0
    assert tensile["target_source"] == "kullanici_girisi"
    assert seal["target_min"] == 5.0
    assert seal["target_max"] is None
