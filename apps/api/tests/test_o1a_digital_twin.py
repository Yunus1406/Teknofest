"""Faz O.1 (Madde 18) — Ambalajın Dijital İkizi. Yeni bir tablo YOK; bu
servis mevcut traceability_service + ProcessReference + SustainabilityResult
+ version_history'yi birleştirir. Kritik davranış: statik bir anlık görüntü
DEĞİL, canlı bir görünüm -- reçetenin yeni bir versiyonu açıldığında (V1->V2)
her iki versiyonun kendi twin'i DB'nin GÜNCEL halini yansıtır."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.production import ProductionOrder, SustainabilityResult
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.models.technical_reference import ProcessReference
from app.services.digital_twin_service import build_digital_twin
from app.services.production_flow_service import submit_physical_tests


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
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    material = Material(
        polymer_id=polymer.id, name="Test Malzeme O1a", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(material)
    db.flush()
    return material


def _line(db, process_type="Blown Film Extrusion"):
    line = ProductionLine(
        name="Test Hat O1a", process_type=process_type, layer_structure="A",
        layer_count=1, min_micron=20.0, max_micron=100.0,
    )
    db.add(line)
    db.flush()
    return line


def _recipe(db, line, material, packaging_type="esnek film ambalaj", version=1, parent_recipe_id=None):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=version, parent_recipe_id=parent_recipe_id,
        line_id=line.id, source="sistem_uretti", status="dogrulandi", is_verified=(version == 1),
        total_micron=70.0,
    )
    db.add(recipe)
    db.flush()
    db.add(
        RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0)
    )
    db.commit()
    db.refresh(recipe)
    return recipe


def test_digital_twin_combines_all_pieces(db_session):
    line = _line(db_session)
    db_session.add(
        ProcessReference(process_type="Blown Film Extrusion", parameter_name="Eritme Sıcaklığı", typical_min=180.0, typical_max=220.0, unit="°C")
    )
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)
    db_session.add(
        SustainabilityResult(
            recipe_id=recipe.id,
            per_1000_units={"virgin_kg": 10.0, "pcr_kg": 0.0, "regranul_kg": 0.0, "karbon_kg_co2": 20.0, "fire_kg": 1.0, "enerji_kwh": 5.0},
            is_actual=True,
        )
    )
    db_session.commit()

    twin = build_digital_twin(db_session, recipe.id)

    assert twin is not None
    assert twin["traceability"]["recipe"]["id"] == recipe.id
    assert twin["traceability"]["machine"]["process_type"] == "Blown Film Extrusion"
    assert len(twin["process_parameters"]) == 1
    assert twin["process_parameters"][0]["parameter_name"] == "Eritme Sıcaklığı"
    assert twin["sustainability_per_1000_units"]["is_actual"] is True
    assert twin["sustainability_per_1000_units"]["karbon_kg_co2"] == 20.0
    assert twin["version_history"] == [
        {"id": recipe.id, "version": 1, "status": "dogrulandi", "is_verified": True, "created_at": recipe.created_at.isoformat()}
    ]


def test_digital_twin_unknown_recipe_returns_none(db_session):
    assert build_digital_twin(db_session, "olmayan-recipe-id") is None


def test_http_digital_twin_endpoint_returns_200(client, db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)

    resp = client.get(f"/api/v1/traceability/recipes/{recipe.id}/digital-twin")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["traceability"]["recipe_id"] == recipe.id
    assert body["process_parameters"] == []
    assert body["sustainability_per_1000_units"] is None
    assert len(body["version_history"]) == 1


def test_http_digital_twin_endpoint_404_for_unknown_recipe(client):
    resp = client.get("/api/v1/traceability/recipes/olmayan-recipe-id/digital-twin")
    assert resp.status_code == 404


def test_digital_twin_falls_back_to_estimated_sustainability_when_no_actual(db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)
    db_session.add(
        SustainabilityResult(
            recipe_id=recipe.id,
            per_1000_units={"virgin_kg": 10.0, "karbon_kg_co2": 18.0},
            is_actual=False,
        )
    )
    db_session.commit()

    twin = build_digital_twin(db_session, recipe.id)
    assert twin["sustainability_per_1000_units"]["is_actual"] is False
    assert twin["sustainability_per_1000_units"]["karbon_kg_co2"] == 18.0


def test_digital_twin_is_live_not_a_static_snapshot(db_session):
    """V1 için twin çekilir; ardından bir fiziksel test BAŞARISIZ olur ve
    V2 taslak olarak açılır (bkz. submit_physical_tests). V1'in kendi
    twin'i DEĞİŞMEZ (kendi test/versiyon geçmişi gerçekten değişmedi);
    V2'nin twin'i ise HİÇBİR önbellek/yeniden hesaplama tetiklenmeden
    anında doğru veriyi taşır -- bu, görünümün statik değil canlı
    olduğunu kanıtlar."""
    line = _line(db_session)
    material = _material(db_session)
    recipe_v1 = _recipe(db_session, line, material)

    twin_v1_before = build_digital_twin(db_session, recipe_v1.id)
    assert twin_v1_before["version_history"] == [
        {"id": recipe_v1.id, "version": 1, "status": "dogrulandi", "is_verified": True, "created_at": recipe_v1.created_at.isoformat()}
    ]
    assert twin_v1_before["traceability"]["physical_tests"] == []

    order = ProductionOrder(recipe_id=recipe_v1.id, line_id=line.id, status="tamamlandi", scheduled_qty_units=1000)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    _, new_version = submit_physical_tests(
        db_session, order,
        [{"test_type": "kalinlik", "value": 90.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0}],
    )
    assert new_version is not None

    twin_v1_after = build_digital_twin(db_session, recipe_v1.id)
    assert len(twin_v1_after["traceability"]["physical_tests"]) == 1
    # V1'in kendi durumu GERÇEKTEN "revizyon_gerekli"ye döndü (bkz.
    # submit_physical_tests) -- twin bunu HİÇBİR önbellek/yeniden hesaplama
    # adımı olmadan anında yansıtıyor; bu da "canlı" olduğunun kanıtı.
    assert twin_v1_after["version_history"][0]["status"] == "revizyon_gerekli"
    assert [v["version"] for v in twin_v1_after["version_history"]] == [1]

    twin_v2 = build_digital_twin(db_session, new_version.id)
    assert twin_v2["traceability"]["physical_tests"] == [], "V2 kendi ayrı test geçmişiyle başlar"
    assert [v["version"] for v in twin_v2["version_history"]] == [1, 2], (
        "V2'nin görünümü YENİ açılan versiyonu ANINDA, ekstra bir adım olmadan yansıtmalı"
    )
