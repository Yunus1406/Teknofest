"""Faz R.2 (Madde 27) — Dijital Uygunluk Dosyası. 11 kalemin her biri
GERÇEK veriden ✓/⚠/✕ durumu türetir; SKU'nun hiç doğrulanmış reçetesi yoksa
çoğu kalem dürüstçe "eksik" döner (uydurulmaz)."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer, Regulation
from app.models.product_sku import ProductSku
from app.models.production import PhysicalTest, ProductionOrder
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer, RegulatoryAssessment
from app.models.regulation_requirement import RegulationRequirement
from app.services.compliance_dossier_service import build_compliance_dossier


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _polymer(db):
    p = db.query(Polymer).filter_by(code="PE").one_or_none()
    if p is None:
        p = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
        db.add(p)
        db.flush()
    return p


def _material(db, **kwargs):
    polymer = _polymer(db)
    defaults = dict(
        polymer_id=polymer.id, name="Test Malzeme", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    defaults.update(kwargs)
    m = Material(**defaults)
    db.add(m)
    db.flush()
    return m


def _sku(db, code="SKU-1"):
    sku = ProductSku(sku_code=code, product_name="Test Ürün", packaging_type="plastik tabak", usage_area="x", target_market="AB")
    db.add(sku)
    db.flush()
    return sku


def _request(db, sku, food_contact=True):
    req = PackagingRequest(
        packaging_type="plastik tabak", usage_area="test", product="test ürün", target_market="AB",
        food_contact=food_contact, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100}, sku_id=sku.id,
    )
    db.add(req)
    db.flush()
    return req


def _recipe(db, req, material, is_verified=True):
    recipe = Recipe(packaging_request_id=req.id, version=1, source="sistem_uretti", status="dogrulandi", is_verified=is_verified, total_micron=70.0)
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_unknown_sku_returns_none(db_session):
    assert build_compliance_dossier(db_session, "olmayan-id") is None


def test_sku_without_recipe_has_mostly_missing_items(db_session):
    sku = _sku(db_session)
    db_session.commit()

    dossier = build_compliance_dossier(db_session, sku.id)

    by_key = {i["key"]: i for i in dossier["items"]}
    assert len(dossier["items"]) == 11
    assert by_key["recete"]["durum"] == "eksik"
    assert by_key["hammadde"]["durum"] == "eksik"
    assert by_key["tedarikci_belgeleri"]["durum"] == "eksik"
    assert by_key["ppwr_kontrolleri"]["durum"] == "eksik"
    assert by_key["gida_temas_kontrolleri"]["durum"] == "eksik"
    assert by_key["testler"]["durum"] == "eksik"
    assert by_key["karbon_hesabi"]["durum"] == "eksik"
    assert by_key["uretim_kayitlari"]["durum"] == "eksik"
    assert by_key["mevzuat_surumleri"]["durum"] == "eksik"
    assert by_key["degisiklik_gecmisi"]["durum"] == "eksik"


def test_verified_recipe_marks_recete_and_hammadde_tamam(db_session):
    sku = _sku(db_session)
    req = _request(db_session, sku, food_contact=False)
    material = _material(db_session, technical_datasheet_ref="TDS-1")
    recipe = _recipe(db_session, req, material, is_verified=True)
    sku.current_recipe_id = recipe.id
    db_session.commit()

    dossier = build_compliance_dossier(db_session, sku.id)
    by_key = {i["key"]: i for i in dossier["items"]}

    assert by_key["recete"]["durum"] == "tamam"
    assert by_key["hammadde"]["durum"] == "tamam"
    # Gıda temaslı değil -- kontrol gerekmiyor, dürüstçe "tamam".
    assert by_key["gida_temas_kontrolleri"]["durum"] == "tamam"


def test_unverified_recipe_is_kismi_not_fabricated_tamam(db_session):
    sku = _sku(db_session)
    req = _request(db_session, sku, food_contact=False)
    material = _material(db_session)
    recipe = _recipe(db_session, req, material, is_verified=False)
    sku.current_recipe_id = recipe.id
    db_session.commit()

    dossier = build_compliance_dossier(db_session, sku.id)
    by_key = {i["key"]: i for i in dossier["items"]}
    assert by_key["recete"]["durum"] == "kismi"


def test_failed_physical_test_marks_testler_eksik(db_session):
    sku = _sku(db_session)
    req = _request(db_session, sku, food_contact=False)
    material = _material(db_session)
    recipe = _recipe(db_session, req, material)
    sku.current_recipe_id = recipe.id
    db_session.add(PhysicalTest(recipe_id=recipe.id, test_type="kalinlik", value=50.0, unit="mikron", target_min=60.0, target_max=80.0, result="basarisiz", passed=False))
    db_session.commit()

    dossier = build_compliance_dossier(db_session, sku.id)
    by_key = {i["key"]: i for i in dossier["items"]}
    assert by_key["testler"]["durum"] == "eksik"


def test_completed_production_order_marks_uretim_kayitlari_tamam(db_session):
    sku = _sku(db_session)
    req = _request(db_session, sku, food_contact=False)
    material = _material(db_session)
    recipe = _recipe(db_session, req, material)
    sku.current_recipe_id = recipe.id
    line = ProductionLine(name="Hat-1", layer_structure="A", layer_count=1, min_micron=10.0, max_micron=200.0)
    db_session.add(line)
    db_session.flush()
    db_session.add(ProductionOrder(recipe_id=recipe.id, line_id=line.id, status="tamamlandi", scheduled_qty_units=100))
    db_session.commit()

    dossier = build_compliance_dossier(db_session, sku.id)
    by_key = {i["key"]: i for i in dossier["items"]}
    assert by_key["uretim_kayitlari"]["durum"] == "tamam"


def test_outdated_regulation_version_marks_mevzuat_surumleri_eksik(db_session):
    sku = _sku(db_session)
    req = _request(db_session, sku, food_contact=False)
    material = _material(db_session)
    recipe = _recipe(db_session, req, material)
    sku.current_recipe_id = recipe.id

    reg = Regulation(code="PPWR-ART-77", title="Test Madde", category="test", description="d")
    db_session.add(reg)
    db_session.flush()
    db_session.add(RegulationRequirement(
        regulation_id=reg.id, regulation_no="EU 1", article="Md.1", requirement_text="t",
        version="2.0", previous_version="1.0", changed_at=datetime(2026, 1, 1, tzinfo=timezone.utc), change_summary="Değişti.",
    ))
    db_session.add(RegulatoryAssessment(
        packaging_request_id=req.id, regulation_id=reg.id, verdict="uygun_gorunuyor", reasoning="t",
        regulation_version_snapshot="1.0",
    ))
    db_session.commit()

    dossier = build_compliance_dossier(db_session, sku.id)
    by_key = {i["key"]: i for i in dossier["items"]}
    assert by_key["mevzuat_surumleri"]["durum"] == "eksik"
    # Değişiklik geçmişinin KENDİSİ mevcut/izlenebilir olduğu için "tamam" --
    # 10. kalemden (versiyon güncelliği) farklı bir soruya cevap verir.
    assert by_key["degisiklik_gecmisi"]["durum"] == "tamam"
    assert "1 tanesi" in by_key["degisiklik_gecmisi"]["aciklama"]


def test_http_compliance_dossier_endpoint(client, db_session):
    sku = _sku(db_session, code="SKU-HTTP")
    db_session.commit()

    resp = client.get(f"/api/v1/product-skus/{sku.id}/compliance-dossier")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sku_code"] == "SKU-HTTP"
    assert len(body["items"]) == 11


def test_http_compliance_dossier_404_for_unknown_sku(client):
    resp = client.get("/api/v1/product-skus/olmayan-id/compliance-dossier")
    assert resp.status_code == 404
