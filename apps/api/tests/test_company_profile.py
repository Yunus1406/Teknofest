"""Faz E.1 — Firma Profili API'si: tek kiracılı singleton Company/Facility
CRUD'u. `bool | None` alanların set edilmediğinde `None` (asla `False`)
kaldığı ve `GET`in Company yokken 404 (sessizce boş bir satır OLUŞTURMADIĞI)
döndüğü doğrulanır."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_get_profile_404_when_no_company_exists(client):
    resp = client.get("/api/v1/company/profile")
    assert resp.status_code == 404


def test_create_profile_then_get(client):
    resp = client.post("/api/v1/company/profile", json={"name": "Test Ambalaj A.Ş."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["company"]["name"] == "Test Ambalaj A.Ş."
    # Set edilmemiş boolean alanlar None kalmalı -- asla False varsayılmaz.
    assert body["company"]["exports_to_eu"] is None
    assert body["company"]["produces_food_packaging"] is None

    resp2 = client.get("/api/v1/company/profile")
    assert resp2.status_code == 200
    assert resp2.json()["company"]["name"] == "Test Ambalaj A.Ş."


def test_create_profile_twice_rejected(client):
    client.post("/api/v1/company/profile", json={"name": "İlk Firma"})
    resp = client.post("/api/v1/company/profile", json={"name": "İkinci Firma"})
    assert resp.status_code == 400


def test_update_profile_sets_fields_and_preserves_unset_as_none(client):
    client.post("/api/v1/company/profile", json={"name": "Test Firma"})

    resp = client.put(
        "/api/v1/company/profile",
        json={"trade_name": "TestBrand", "exports_to_eu": True, "employee_count": 42},
    )
    assert resp.status_code == 200
    body = resp.json()["company"]
    assert body["trade_name"] == "TestBrand"
    assert body["exports_to_eu"] is True
    assert body["employee_count"] == 42
    # Hiç dokunulmayan alan hâlâ None -- asla varsayılan bir değere düşmez.
    assert body["produces_food_packaging"] is None


def test_update_profile_404_when_no_company_exists(client):
    resp = client.put("/api/v1/company/profile", json={"trade_name": "X"})
    assert resp.status_code == 404


def test_create_and_update_facility(client):
    client.post("/api/v1/company/profile", json={"name": "Test Firma"})

    resp = client.post(
        "/api/v1/company/facilities",
        json={"name": "Merkez Tesis", "code": "T1", "shift_count": 2},
    )
    assert resp.status_code == 200
    facility = resp.json()
    assert facility["name"] == "Merkez Tesis"
    assert facility["shift_count"] == 2
    assert facility["renewable_energy_used"] is None

    resp2 = client.put(
        f"/api/v1/company/facilities/{facility['id']}",
        json={"name": "Merkez Tesis", "renewable_energy_used": True, "renewable_energy_pct": 30.0},
    )
    assert resp2.status_code == 200
    assert resp2.json()["renewable_energy_used"] is True
    assert resp2.json()["renewable_energy_pct"] == 30.0

    profile = client.get("/api/v1/company/profile").json()
    assert len(profile["facilities"]) == 1


def test_create_facility_requires_existing_company(client):
    resp = client.post("/api/v1/company/facilities", json={"name": "Tesis"})
    assert resp.status_code == 404


def test_update_unknown_facility_404(client):
    client.post("/api/v1/company/profile", json={"name": "Test Firma"})
    resp = client.put("/api/v1/company/facilities/does-not-exist", json={"name": "X"})
    assert resp.status_code == 404
