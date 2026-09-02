"""Faz G.1 — Aşama 2 "Çıkarılan Bilgileri Kontrol Edin" ekranının backend
tarafı: yeni kalınlık/gramaj/fiziksel performans alanları create/update'te
doğru taşınıyor mu, LLM çıkarım şeması bu alanları da kapsıyor mu."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.llm.spec_extraction import extract_fields_from_spec_text
from app.main import app
from app.models.recipe import PackagingRequest
from app.services.packaging_service import create_packaging_request, update_packaging_request


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_create_packaging_request_stores_new_review_fields(db_session):
    req = create_packaging_request(
        db_session,
        {
            "packaging_type": "plastik tabak", "usage_area": "test", "product": "test",
            "target_market": "AB", "food_contact": True, "target_volume_units": 1000,
            "dimensions": {}, "target_thickness_micron": 600.0, "target_gsm": 45.0,
            "physical_performance_notes": "Sıcak dolum, -18°C dondurucuya dayanıklı olmalı.",
        },
    )
    assert req.target_thickness_micron == 600.0
    assert req.target_gsm == 45.0
    assert "dondurucuya" in req.physical_performance_notes


def test_update_packaging_request_can_set_review_fields(db_session):
    req = create_packaging_request(
        db_session,
        {
            "packaging_type": "plastik tabak", "usage_area": "test", "product": "test",
            "target_market": "AB", "food_contact": True, "target_volume_units": 1000,
            "dimensions": {},
        },
    )
    assert req.target_thickness_micron is None

    updated = update_packaging_request(
        db_session, req, {"target_thickness_micron": 70.0, "target_gsm": 12.5, "physical_performance_notes": "Not."}
    )
    assert updated.target_thickness_micron == 70.0
    assert updated.target_gsm == 12.5
    assert updated.physical_performance_notes == "Not."


def test_spec_extraction_result_includes_new_fields_when_llm_unavailable():
    """LLM mevcut değilken (bu test ortamında olduğu gibi) boş sonuç bile
    yeni 3 alanı taşımalı -- schema tam, değer sadece None."""
    result = extract_fields_from_spec_text("herhangi bir şartname metni")
    assert "target_thickness_micron" in result
    assert "target_gsm" in result
    assert "physical_performance_notes" in result
    assert result["target_thickness_micron"] is None


def test_spec_extraction_regex_fallback_fills_fields_when_llm_unavailable():
    """Faz K.1 — LLM yokken (bu ortamda hep) "Alanları Çıkar" artık TAMAMEN
    boş dönmemeli; regex/anahtar-kelime tabanlı bir fallback en azından net
    bir şekilde metinde geçen alanları düşük güvenle doldurmalı. Düzeltmeden
    önce bu fonksiyon koşulsuz _EMPTY_RESULT dönüyordu -- bu test o hatayı
    üretir ve kilitler."""
    text = (
        "Bu ürün Avrupa Birliği (AB) pazarına yönelik gıda temaslı bir "
        "plastik tabak olacak. Hedef kalınlık 450 mikron, üretim miktarı "
        "500.000 adet olarak planlanıyor."
    )
    result = extract_fields_from_spec_text(text)

    assert result["packaging_type"] == "tabak"
    assert result["target_market"] == "AB"
    assert result["food_contact"] is True
    assert result["target_thickness_micron"] == 450.0
    assert result["target_volume_units"] == 500000
    # Her bulunan alan düşük güvenle işaretlenmeli -- kullanıcı doğrulamalı.
    for field in ("packaging_type", "target_market", "food_contact", "target_thickness_micron", "target_volume_units"):
        assert result["field_confidence"][field] == "dusuk"


def test_spec_extraction_regex_fallback_leaves_unfound_fields_none():
    """Metinde hiçbir tanınan kalıp yoksa hiçbir alan UYDURULMAMALI."""
    result = extract_fields_from_spec_text("bu metinde hiçbir tanınan bilgi yok")
    assert result["packaging_type"] is None
    assert result["target_market"] is None
    assert result["target_thickness_micron"] is None
    assert result["field_confidence"] == {}


def test_packaging_request_endpoints_roundtrip_review_fields(client, db_session):
    resp = client.post(
        "/api/v1/packaging-flow/requests",
        json={
            "packaging_type": "plastik tabak", "usage_area": "yemek servisi", "product": "test",
            "target_market": "AB", "food_contact": True, "target_volume_units": 1000,
            "dimensions": {}, "target_thickness_micron": 500.0, "target_gsm": 40.0,
            "physical_performance_notes": "Test notu.",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_thickness_micron"] == 500.0
    assert body["target_gsm"] == 40.0

    req_id = body["id"]
    resp2 = client.put(
        f"/api/v1/packaging-flow/requests/{req_id}",
        json={
            "packaging_type": "plastik tabak", "usage_area": "yemek servisi", "product": "test",
            "target_market": "AB", "food_contact": True, "target_volume_units": 1000,
            "dimensions": {}, "target_thickness_micron": 550.0, "target_gsm": 42.0,
            "physical_performance_notes": "Güncellenmiş not.",
        },
    )
    assert resp2.status_code == 200
    assert resp2.json()["target_thickness_micron"] == 550.0
    assert resp2.json()["physical_performance_notes"] == "Güncellenmiş not."


# --- Mekanik Test Kabul Kriterleri -------------------------------------------

def test_create_packaging_request_stores_mechanical_test_criteria(db_session):
    req = create_packaging_request(
        db_session,
        {
            "packaging_type": "plastik tabak", "usage_area": "test", "product": "test",
            "target_market": "AB", "food_contact": True, "target_volume_units": 1000,
            "dimensions": {}, "mechanical_test_criteria": {"tensile": {"min": 25.0, "max": None}},
        },
    )
    assert req.mechanical_test_criteria == {"tensile": {"min": 25.0, "max": None}}


def test_packaging_request_defaults_to_empty_mechanical_criteria(db_session):
    req = create_packaging_request(
        db_session,
        {
            "packaging_type": "plastik tabak", "usage_area": "test", "product": "test",
            "target_market": "AB", "food_contact": True, "target_volume_units": 1000, "dimensions": {},
        },
    )
    assert req.mechanical_test_criteria == {}


def test_update_packaging_request_can_set_mechanical_test_criteria(db_session):
    req = create_packaging_request(
        db_session,
        {
            "packaging_type": "plastik tabak", "usage_area": "test", "product": "test",
            "target_market": "AB", "food_contact": True, "target_volume_units": 1000, "dimensions": {},
        },
    )
    updated = update_packaging_request(
        db_session, req, {"mechanical_test_criteria": {"seal": {"min": 5.0, "max": 12.0}}}
    )
    assert updated.mechanical_test_criteria == {"seal": {"min": 5.0, "max": 12.0}}


def test_mechanical_test_criteria_endpoint_roundtrip(client, db_session):
    resp = client.post(
        "/api/v1/packaging-flow/requests",
        json={
            "packaging_type": "plastik tabak", "usage_area": "yemek servisi", "product": "test",
            "target_market": "AB", "food_contact": True, "target_volume_units": 1000,
            "dimensions": {}, "mechanical_test_criteria": {"tensile": {"min": 25.0, "max": 40.0}},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["mechanical_test_criteria"] == {"tensile": {"min": 25.0, "max": 40.0}}
