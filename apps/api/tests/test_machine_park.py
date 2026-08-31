"""Faz E.2 — Makine Parkı: "Yeni Makine Ekle"/güncelleme uçları ve yeni
opsiyonel teknik kart alanlarının boş kalmasının optimizasyon motorunu
(Faz D.1'de düzeltilen candidate_generator.py) bozmadığı doğrulanır."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.infrastructure import LineMaterialCompatibility
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest
from app.services import optimization_service


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_create_production_line_minimal_fields(client):
    resp = client.post(
        "/api/v1/production-lines",
        json={"name": "Test Hat", "layer_structure": "A", "min_micron": 10, "max_micron": 100},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Test Hat"
    # Yeni Faz E.2 alanlarının hiçbiri set edilmedi -- hepsi None kalmalı.
    assert body["manufacturer"] is None
    assert body["pcr_capable"] is None
    assert body["suitable_polymer_codes"] == []


def test_create_production_line_with_full_technical_card(client):
    resp = client.post(
        "/api/v1/production-lines",
        json={
            "name": "Test Hat Full", "layer_structure": "A/B/A", "min_micron": 50, "max_micron": 90,
            "manufacturer": "Windmöller & Hölscher", "model": "Varex II", "install_year": 2019,
            "min_line_speed_m_min": 80.0, "max_line_speed_m_min": 250.0,
            "layer_structure_type": "ABA", "screw_diameter_mm": 60.0, "ld_ratio": 30.0,
            "suitable_polymer_codes": ["PE", "PP"], "pcr_capable": True, "pir_capable": True,
            "max_pcr_technical_pct": 50.0, "gravimetric_dosing_equipped": True,
            "availability_status": "aktif",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["manufacturer"] == "Windmöller & Hölscher"
    assert body["pcr_capable"] is True
    assert body["suitable_polymer_codes"] == ["PE", "PP"]
    assert body["availability_status"] == "aktif"


def test_update_production_line_partial(client):
    create_resp = client.post(
        "/api/v1/production-lines",
        json={"name": "Test Hat", "layer_structure": "A", "min_micron": 10, "max_micron": 100},
    )
    line_id = create_resp.json()["id"]

    resp = client.put(f"/api/v1/production-lines/{line_id}", json={"manufacturer": "Reifenhäuser"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["manufacturer"] == "Reifenhäuser"
    assert body["name"] == "Test Hat"  # dokunulmayan alan korunuyor


def test_update_unknown_production_line_404(client):
    resp = client.put("/api/v1/production-lines/does-not-exist", json={"manufacturer": "X"})
    assert resp.status_code == 404


# --- Yeni opsiyonel alanlar boş kalınca optimizasyon motoru hâlâ çalışıyor --

def test_optimization_still_works_when_new_machine_fields_are_unset(client, db_session):
    """`POST /production-lines`'ın minimal alanlarla oluşturduğu bir hat,
    Faz D.1'de düzeltilen candidate_generator.py ile hâlâ aday üretebilmeli
    -- yeni E.2 alanlarının hiçbiri okunmuyor, sadece mevcut zorunlu
    alanlara (layer_structure, min/max_micron, material_compatibility)
    bakılıyor."""
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()
    virgin = Material(
        polymer_id=polymer.id, name="PE Virgin Test", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db_session.add(virgin)
    db_session.flush()

    resp = client.post(
        "/api/v1/production-lines",
        json={
            "name": "E2 Test Hat", "layer_structure": "A", "min_micron": 50, "max_micron": 90,
            "supported_packaging_types": ["esnek_film_ambalaj"],
        },
    )
    line_id = resp.json()["id"]
    db_session.add(LineMaterialCompatibility(line_id=line_id, material_id=virgin.id, max_ratio_pct=100.0))

    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db_session.add(req)
    db_session.commit()

    result = optimization_service.run_optimization(db_session, req.id, line_id, ratio_step_pct=10)

    assert result["generated_candidate_count"] > 0
