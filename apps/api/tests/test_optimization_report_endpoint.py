"""Faz C.7 — `GET /production-flow/recipes/{id}/optimization-report`
endpoint'i. `application/pdf` içerik tipi + doğru dosya adı header'ı,
doğrulanmamış reçetede 400, ve pasaport varsa QR'ın PDF'e eklendiği
(pasaport yoksa eklenmediği) doğrulanır."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.knowledge import Material, Polymer
from app.models.production import SustainabilityResult
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.passport_service import get_or_create_passport


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
    material = Material(
        polymer_id=polymer.id, name="Test Malzeme", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(material)
    db.flush()
    return material


def _verified_recipe(db, is_verified=True):
    material = _material(db)
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, source="sistem_uretti",
        status="dogrulandi" if is_verified else "onerildi", is_verified=is_verified, total_micron=70.0,
    )
    db.add(recipe)
    db.flush()
    db.add(
        RecipeLayer(
            recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id,
            ratio_pct=100.0, thickness_micron=70.0,
        )
    )
    if is_verified:
        db.add(
            SustainabilityResult(
                recipe_id=recipe.id,
                per_1000_units={
                    "virgin_kg": 10.0, "pcr_kg": 0.0, "regranul_kg": 0.0, "karbon_kg_co2": 18.0,
                    "karbon_veri_kalitesi": "tanimli_demo", "fire_kg": 1.0, "enerji_kwh": 5.0,
                },
                is_actual=True,
            )
        )
    db.commit()
    db.refresh(recipe)
    return recipe


def test_technical_report_returns_pdf_with_correct_headers(client, db_session):
    recipe = _verified_recipe(db_session)

    resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/optimization-report")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    assert recipe.id[:8] in resp.headers["content-disposition"]
    assert resp.content[:5] == b"%PDF-"


def test_executive_summary_format_returns_pdf(client, db_session):
    recipe = _verified_recipe(db_session)

    resp = client.get(
        f"/api/v1/production-flow/recipes/{recipe.id}/optimization-report", params={"format": "executive"}
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "yonetici-ozeti" in resp.headers["content-disposition"]
    assert resp.content[:5] == b"%PDF-"


def test_report_for_unverified_recipe_returns_400(client, db_session):
    recipe = _verified_recipe(db_session, is_verified=False)

    resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/optimization-report")

    assert resp.status_code == 400


def test_report_for_unknown_recipe_returns_404(client):
    resp = client.get("/api/v1/production-flow/recipes/does-not-exist/optimization-report")
    assert resp.status_code == 404


def test_report_includes_qr_page_when_passport_exists(client, db_session):
    recipe = _verified_recipe(db_session)
    get_or_create_passport(db_session, recipe.id)

    resp_without = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/optimization-report")

    # Aynı reçete için tekrar pasaport oluşturulmadan önceki hâliyle
    # karşılaştırmak yerine, pasaportsuz bir reçeteyle sayfa sayısını
    # karşılaştırıyoruz -- iki ayrı reçete, biri pasaportlu biri değil.
    other_recipe = _verified_recipe(db_session)
    resp_other_without_passport = client.get(
        f"/api/v1/production-flow/recipes/{other_recipe.id}/optimization-report"
    )

    from pypdf import PdfReader
    from io import BytesIO

    pages_with = len(PdfReader(BytesIO(resp_without.content)).pages)
    pages_without = len(PdfReader(BytesIO(resp_other_without_passport.content)).pages)

    assert pages_with > pages_without
