"""Faz P.1 (Madde 20) — Senaryo Laboratuvarı. Gerçek optimizasyon motorunun
(RecipeCandidate/scorer.score_candidate) AYNI parçalarını reuse eder; mock
bir hesap değildir. Kritik davranışlar: (a) yeterli veri varken senaryo
gerçek formüllerle hesaplanır, (b) PCR malzeme verisi eksikse o boyut
UYDURULMAZ (açık bir uyarıyla), (c) HİÇBİR ŞEY DB'ye yazılmaz."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.infrastructure import ProductionLine
from app.models.knowledge import CarbonEmissionFactor, Material, Polymer, Regulation
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.scenario_service import run_scenario


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


def _material(db, material_type, name, max_recommended_ratio_pct=100.0, cost_per_kg=30.0, carbon=1.8):
    polymer = _polymer(db)
    m = Material(
        polymer_id=polymer.id, name=name, material_type=material_type,
        food_contact_eligible=True, max_recommended_ratio_pct=max_recommended_ratio_pct,
        cost_per_kg=cost_per_kg, carbon_factor_kg_co2_per_kg=carbon,
    )
    db.add(m)
    db.flush()
    return m


def _line(db, min_micron=20.0, max_micron=100.0, facility=None):
    line = ProductionLine(
        name="Test Hat P1a", process_type="Blown Film Extrusion", layer_structure="A/B",
        layer_count=2, min_micron=min_micron, max_micron=max_micron,
        facility_id=facility.id if facility else None,
    )
    db.add(line)
    db.flush()
    return line


def _recipe(db, line, virgin_material, pcr_material=None, total_micron=70.0, food_contact=True):
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test ürün", target_market="AB",
        food_contact=food_contact, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, line_id=line.id, source="sistem_uretti",
        status="dogrulandi", is_verified=True, total_micron=total_micron,
    )
    db.add(recipe)
    db.flush()
    if pcr_material is not None:
        db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=virgin_material.id, ratio_pct=100.0, thickness_micron=total_micron * 0.7))
        db.add(RecipeLayer(recipe_id=recipe.id, layer_index=1, layer_label="B", material_id=pcr_material.id, ratio_pct=100.0, thickness_micron=total_micron * 0.3))
    else:
        db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=virgin_material.id, ratio_pct=100.0, thickness_micron=total_micron))
    db.commit()
    db.refresh(recipe)
    return recipe


def _ppwr_art7(db, target_2030=10.0):
    reg = Regulation(
        code="PPWR-ART-7", title="Geri Dönüştürülmüş İçerik", category="geri_donusturulmus_icerik",
        description="test",
        criteria={"targets": [{"food_contact": True, "pet": False, "by_year": {"2030": target_2030, "2040": 25.0}}]},
    )
    db.add(reg)
    db.commit()
    return reg


def _grid_ef(db, value=0.42):
    ef = CarbonEmissionFactor(
        material_key="Elektrik (TR Şebeke Karışımı)", factor_type="elektrik", ef_value=value,
        unit="kg_co2e_per_kwh", source="TR şebeke ortalaması", year=2023, version="1.0", is_demo_placeholder=True,
    )
    db.add(ef)
    db.commit()
    return ef


def test_scenario_with_full_data_computes_real_deltas(db_session):
    virgin = _material(db_session, "virgin", "Virgin PE", cost_per_kg=30.0, carbon=1.8)
    pcr = _material(db_session, "pcr", "PCR PE", max_recommended_ratio_pct=40.0, cost_per_kg=20.0, carbon=0.9)
    line = _line(db_session)
    recipe = _recipe(db_session, line, virgin, pcr)
    _ppwr_art7(db_session, target_2030=10.0)
    _grid_ef(db_session)

    result = run_scenario(db_session, recipe.id, {"pcr_pct": 50.0, "kalinlik_micron": 60.0, "fire_pct": 2.0, "yenilenebilir_enerji_pct": 50.0})

    assert result is not None
    assert result["baseline"]["pcr_pct"] == 30.0  # 0.3 katman payı, ratio_pct=100
    assert result["senaryo"]["pcr_pct"] == 50.0
    assert result["senaryo"]["total_micron"] == 60.0
    assert result["fark"]["pcr_pct"] == 20.0
    # PCR daha ucuz/düşük karbonlu -> senaryo maliyeti/karbonu baseline'dan düşük olmalı
    assert result["senaryo"]["maliyet_tl_per_kg"] < result["baseline"]["maliyet_tl_per_kg"]
    assert result["senaryo"]["karbon_kg_co2_per_kg"] < result["baseline"]["karbon_kg_co2_per_kg"]
    assert result["baseline"]["veri_kaynagi"] == "hesaplanan"
    assert result["senaryo"]["veri_kaynagi"] == "senaryo_simulasyonu"
    assert result["mevzuat"]["hedef_pct"] == 10.0
    assert result["mevzuat"]["hedefi_karsiliyor_mu"] is True
    assert result["uyarilar"] == []


def test_scenario_pcr_target_without_pcr_material_is_not_fabricated(db_session):
    virgin = _material(db_session, "virgin", "Virgin PE")
    line = _line(db_session)
    recipe = _recipe(db_session, line, virgin, pcr_material=None)

    result = run_scenario(db_session, recipe.id, {"pcr_pct": 30.0})

    assert result["senaryo"]["pcr_pct"] == 0.0  # değişmedi, uydurulmadı
    assert len(result["uyarilar"]) == 1
    assert "PCR malzemesi yok" in result["uyarilar"][0]


def test_scenario_technical_risk_flags_thickness_outside_line_range(db_session):
    virgin = _material(db_session, "virgin", "Virgin PE")
    pcr = _material(db_session, "pcr", "PCR PE", max_recommended_ratio_pct=40.0)
    line = _line(db_session, min_micron=50.0, max_micron=80.0)
    recipe = _recipe(db_session, line, virgin, pcr)

    result = run_scenario(db_session, recipe.id, {"kalinlik_micron": 30.0})

    assert result["teknik_risk"]["kalinlik_hat_sinirlari_icinde"] is False
    assert len(result["teknik_risk"]["notlar"]) == 1


def test_scenario_does_not_write_to_db(db_session):
    virgin = _material(db_session, "virgin", "Virgin PE")
    line = _line(db_session)
    recipe = _recipe(db_session, line, virgin)

    recipes_before = db_session.query(Recipe).count()
    layers_before = db_session.query(RecipeLayer).count()

    run_scenario(db_session, recipe.id, {"pcr_pct": 10.0, "kalinlik_micron": 60.0})

    assert db_session.query(Recipe).count() == recipes_before
    assert db_session.query(RecipeLayer).count() == layers_before


def test_scenario_rejects_unverified_recipe(db_session):
    virgin = _material(db_session, "virgin", "Virgin PE")
    line = _line(db_session)
    recipe = _recipe(db_session, line, virgin)
    recipe.is_verified = False
    db_session.commit()

    with pytest.raises(ValueError, match="doğrulanmış reçeteler"):
        run_scenario(db_session, recipe.id, {})


def test_scenario_unknown_recipe_returns_none(db_session):
    assert run_scenario(db_session, "olmayan-id", {}) is None


def test_http_scenario_endpoint(client, db_session):
    virgin = _material(db_session, "virgin", "Virgin PE")
    pcr = _material(db_session, "pcr", "PCR PE", max_recommended_ratio_pct=40.0)
    line = _line(db_session)
    recipe = _recipe(db_session, line, virgin, pcr)

    resp = client.post(f"/api/v1/production-flow/recipes/{recipe.id}/scenario", json={"pcr_pct": 40.0})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["senaryo"]["pcr_pct"] == 40.0
    assert body["baseline"]["veri_kaynagi"] == "hesaplanan"
