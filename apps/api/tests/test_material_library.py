"""Faz E.3 — Hammadde ve Malzeme Kütüphanesi: "Yeni Hammadde/Katkı Ekle" ve
güncelleme uçları. Kritik doğrulama: material_type'a göre POST /materials
gerçekten doğru polymorphic alt sınıfı (Material/PcrMaterial/PirMaterial)
yaratıyor -- PCR ve PIR ASLA aynı Python sınıfına yazılmıyor (Faz B.2'nin
STI ayrımı bu fazda da korunuyor)."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.knowledge import Additive, Material, PcrMaterial, PirMaterial, Polymer


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
def polymer(db_session):
    p = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db_session.add(p)
    db_session.commit()
    return p


def test_create_virgin_material_instantiates_base_class(client, db_session, polymer):
    resp = client.post(
        "/api/v1/materials",
        json={"polymer_id": polymer.id, "name": "PE Virgin Test", "material_type": "virgin"},
    )
    assert resp.status_code == 200
    material_id = resp.json()["id"]

    assert db_session.get(Material, material_id) is not None
    assert db_session.get(PcrMaterial, material_id) is None
    assert db_session.get(PirMaterial, material_id) is None


def test_create_pcr_material_instantiates_pcr_subclass(client, db_session, polymer):
    resp = client.post(
        "/api/v1/materials",
        json={
            "polymer_id": polymer.id, "name": "PE PCR Test", "material_type": "pcr",
            "post_consumer_content_pct": 85.0, "contamination_level": "dusuk",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    material_id = body["id"]
    assert body["post_consumer_content_pct"] == 85.0
    assert body["contamination_level"] == "dusuk"

    pcr_row = db_session.get(PcrMaterial, material_id)
    assert pcr_row is not None
    assert pcr_row.post_consumer_content_pct == 85.0
    assert db_session.get(PirMaterial, material_id) is None


def test_create_pir_material_instantiates_pir_subclass(client, db_session, polymer):
    resp = client.post(
        "/api/v1/materials",
        json={
            "polymer_id": polymer.id, "name": "PE PIR Test", "material_type": "regranul",
            "source_process": "Ekstrüzyon Kenar Fire Geri Kazanımı",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    material_id = body["id"]
    assert body["source_process"] == "Ekstrüzyon Kenar Fire Geri Kazanımı"
    # PIR sınıfının post_consumer_content_pct alanı YOK -- payload'da hiç yer almıyor
    assert "post_consumer_content_pct" in body  # şema alanı ortak (None döner)
    assert body["post_consumer_content_pct"] is None

    pir_row = db_session.get(PirMaterial, material_id)
    assert pir_row is not None
    assert db_session.get(PcrMaterial, material_id) is None


def test_post_consumer_content_pct_ignored_for_virgin_material(client, db_session, polymer):
    """PCR'a özgü bir alan, virgin bir hammaddeye gönderilse bile sessizce
    yok sayılır -- Material sınıfının böyle bir sütunu/alanı yoktur (STI)."""
    resp = client.post(
        "/api/v1/materials",
        json={
            "polymer_id": polymer.id, "name": "PE Virgin Ignore Test", "material_type": "virgin",
            "post_consumer_content_pct": 99.0,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["post_consumer_content_pct"] is None


def test_create_material_invalid_type_rejected(client, polymer):
    resp = client.post(
        "/api/v1/materials",
        json={"polymer_id": polymer.id, "name": "Bad Type", "material_type": "unknown"},
    )
    assert resp.status_code == 400


def test_create_material_unknown_polymer_rejected(client):
    resp = client.post(
        "/api/v1/materials",
        json={"polymer_id": "does-not-exist", "name": "X", "material_type": "virgin"},
    )
    assert resp.status_code == 400


def test_update_material_partial(client, db_session, polymer):
    create_resp = client.post(
        "/api/v1/materials",
        json={"polymer_id": polymer.id, "name": "PE Virgin Update Test", "material_type": "virgin"},
    )
    material_id = create_resp.json()["id"]

    resp = client.put(f"/api/v1/materials/{material_id}", json={"origin_country": "Türkiye"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["origin_country"] == "Türkiye"
    assert body["name"] == "PE Virgin Update Test"  # dokunulmayan alan korunuyor


def test_update_material_pcr_only_field_ignored_for_virgin(client, db_session, polymer):
    create_resp = client.post(
        "/api/v1/materials",
        json={"polymer_id": polymer.id, "name": "PE Virgin Update Test 2", "material_type": "virgin"},
    )
    material_id = create_resp.json()["id"]

    resp = client.put(f"/api/v1/materials/{material_id}", json={"post_consumer_content_pct": 50.0})
    assert resp.status_code == 200
    assert resp.json()["post_consumer_content_pct"] is None


def test_update_unknown_material_404(client):
    resp = client.put("/api/v1/materials/does-not-exist", json={"origin_country": "X"})
    assert resp.status_code == 404


def test_create_additive(client, db_session):
    resp = client.post(
        "/api/v1/additives",
        json={"name": "Test Katkı", "additive_type": "stabilizator", "dosage_min_pct": 0.5, "dosage_max_pct": 2.0},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Test Katkı"
    assert db_session.get(Additive, body["id"]) is not None


def test_update_additive_partial(client, db_session):
    create_resp = client.post(
        "/api/v1/additives",
        json={"name": "Test Katkı 2", "additive_type": "stabilizator"},
    )
    additive_id = create_resp.json()["id"]

    resp = client.put(f"/api/v1/additives/{additive_id}", json={"cost_per_kg": 42.0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["cost_per_kg"] == 42.0
    assert body["name"] == "Test Katkı 2"


def test_update_unknown_additive_404(client):
    resp = client.put("/api/v1/additives/does-not-exist", json={"cost_per_kg": 1.0})
    assert resp.status_code == 404
