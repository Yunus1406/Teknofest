"""Faz Q.1 (Madde 23) — Üretim Öncesi Risk Skoru. 7 bileşenin her biri
GERÇEK veriden türetilir; genel risk şeffaf bir kombinasyondur (kara kutu
skor değil, hangi bileşenin riski yükselttiği her zaman görünür)."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.risk_service import compute_risk_score


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _polymer(db, code="PE"):
    p = db.query(Polymer).filter_by(code=code).one_or_none()
    if p is None:
        p = Polymer(code=code, name=code, category="poliolefin", base_properties={})
        db.add(p)
        db.flush()
    return p


def _material(db, material_type="virgin", name=None, cost_per_kg=30.0, carbon=1.8):
    polymer = _polymer(db)
    m = Material(
        polymer_id=polymer.id, name=name or f"Test {material_type}", material_type=material_type,
        food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=cost_per_kg, carbon_factor_kg_co2_per_kg=carbon,
    )
    db.add(m)
    db.flush()
    return m


def _line(db, min_micron=20.0, max_micron=100.0):
    line = ProductionLine(name="Hat-1", process_type="Blown Film Extrusion", layer_structure="A", layer_count=1, min_micron=min_micron, max_micron=max_micron)
    db.add(line)
    db.flush()
    return line


def _recipe(db, line, material, version=1, total_micron=70.0, is_verified=True, food_contact=True, packaging_type="esnek film ambalaj"):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test ürün", target_market="AB",
        food_contact=food_contact, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=version, line_id=line.id if line else None, source="sistem_uretti",
        status="dogrulandi", is_verified=is_verified, total_micron=total_micron,
    )
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=total_micron))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_new_material_flagged_high_risk(db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)

    result = compute_risk_score(db_session, recipe)

    assert result["bilesenler"]["yeni_hammadde"]["risk_katkisi"] == "yuksek"
    assert material.name in result["bilesenler"]["yeni_hammadde"]["deger"]


def test_previously_used_material_is_low_risk(db_session):
    line = _line(db_session)
    material = _material(db_session)
    verified_recipe = _recipe(db_session, line, material, version=1, is_verified=True)

    new_recipe = _recipe(db_session, line, material, version=2, is_verified=False)

    result = compute_risk_score(db_session, new_recipe)
    assert result["bilesenler"]["yeni_hammadde"]["risk_katkisi"] == "dusuk"


def test_no_reference_means_high_similarity_risk_and_no_thickness_claim(db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material, is_verified=False)

    result = compute_risk_score(db_session, recipe)

    assert result["bilesenler"]["gecmis_uretim_benzerligi"]["risk_katkisi"] == "yuksek"
    assert result["bilesenler"]["kalinlik_azaltimi"]["deger"] is None


def test_thickness_reduction_vs_reference_computed_from_real_data(db_session):
    line = _line(db_session)
    material = _material(db_session)
    ref = _recipe(db_session, line, material, version=1, total_micron=100.0, is_verified=True, packaging_type="plastik tabak")

    new_recipe = _recipe(db_session, line, material, version=1, total_micron=80.0, is_verified=False, packaging_type="plastik tabak")

    result = compute_risk_score(db_session, new_recipe)
    dim = result["bilesenler"]["kalinlik_azaltimi"]
    assert dim["deger"] == 20.0  # (100-80)/100*100
    assert dim["risk_katkisi"] == "yuksek"


def test_overall_risk_is_high_when_any_component_is_high(db_session):
    line = _line(db_session)
    material = _material(db_session)  # yeni hammadde -> yuksek
    recipe = _recipe(db_session, line, material, is_verified=False)

    result = compute_risk_score(db_session, recipe)
    assert result["genel_risk"] == "yuksek"


def test_food_contact_evidence_gap_raises_risk(db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material, food_contact=True, is_verified=False)

    result = compute_risk_score(db_session, recipe)
    dim = result["bilesenler"]["mevzuat_kanit_eksikleri"]
    assert dim["deger"] > 0
    assert dim["risk_katkisi"] in ("orta", "yuksek")


def test_http_risk_score_endpoint(client, db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material, is_verified=False)

    resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/risk-score")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["genel_risk"] in ("dusuk", "orta", "yuksek")
    assert set(body["bilesenler"].keys()) == {
        "yeni_hammadde", "pcr_seviyesi", "kalinlik_azaltimi", "makine_uyumu",
        "gecmis_uretim_benzerligi", "teknik_performans", "mevzuat_kanit_eksikleri",
        # Faz R.3 (Madde 28) — additive 8. bileşen.
        "tedarikci_kanit_tamligi",
    }
