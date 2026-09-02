"""Faz R.1 (Madde 26) — Ambalaj Yaşam Döngüsü Zaman Çizelgesi. Yeni bir
tablo/hesap YOK; mevcut olay kaynaklarından (PackagingRequest/
OptimizationRun/ProductionOrder/PhysicalTest/SustainabilityResult/
RegulationRequirement) kronolojik, birleşik bir görünüm türetilir. Bir
olay kaynağı yoksa (ör. hiç optimizasyon koşusu çalıştırılmadıysa) o olay
türü hiç üretilmez."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer, Regulation
from app.models.optimization import OptimizationRun
from app.models.production import ProductionOrder
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer, RegulatoryAssessment
from app.models.regulation_requirement import RegulationRequirement
from app.services.lifecycle_service import build_lifecycle_timeline
from app.services.production_flow_service import finalize_result, submit_physical_tests


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
        polymer_id=polymer.id, name="Test Malzeme R1a", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(material)
    db.flush()
    return material


def _line(db):
    line = ProductionLine(name="Hat-1", layer_structure="A", layer_count=1, min_micron=10.0, max_micron=200.0)
    db.add(line)
    db.flush()
    return line


def _recipe(db, line, material, total_micron=70.0):
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="t", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, line_id=line.id, source="sistem_uretti",
        status="dogrulandi", total_micron=total_micron,
    )
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=total_micron))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_unknown_recipe_returns_none(db_session):
    assert build_lifecycle_timeline(db_session, "olmayan-id") is None


def test_minimal_recipe_has_sartname_and_recete_events(db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)

    events = build_lifecycle_timeline(db_session, recipe.id)

    types = [e["event_type"] for e in events]
    assert "sartname_olusturuldu" in types
    assert "recete_uretildi" in types
    assert "optimizasyon_calistirildi" not in types  # hiç koşu yok, uydurulmadı
    assert "pilot_uretim" not in types  # hiç üretim emri yok
    assert "uretime_serbest_birakildi" not in types  # henüz doğrulanmadı


def test_optimization_run_event_included_when_present(db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)
    run = OptimizationRun(packaging_request_id=recipe.packaging_request_id, parameters={"candidate_count_generated": 12})
    db_session.add(run)
    db_session.commit()

    events = build_lifecycle_timeline(db_session, recipe.id)
    opt_events = [e for e in events if e["event_type"] == "optimizasyon_calistirildi"]
    assert len(opt_events) == 1
    assert opt_events[0]["detay"]["generated_candidate_count"] == 12


def test_events_are_chronologically_sorted(db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)
    order = ProductionOrder(recipe_id=recipe.id, line_id=line.id, status="tamamlandi", scheduled_qty_units=1000)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    submit_physical_tests(
        db_session, order,
        [{"test_type": "kalinlik", "value": 70.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None}],
    )
    finalize_result(db_session, recipe)

    events = build_lifecycle_timeline(db_session, recipe.id)
    dates = [e["tarih"] for e in events]
    assert dates == sorted(dates)

    types = [e["event_type"] for e in events]
    assert "pilot_uretim" in types
    assert "fiziksel_test" in types
    assert "uretime_serbest_birakildi" in types
    # Fiziksel test, üretime serbest bırakmadan ÖNCE gelmeli (gerçek akış).
    assert types.index("fiziksel_test") < types.index("uretime_serbest_birakildi")


def test_revision_after_failed_test_produces_recete_revize_edildi(db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)
    order = ProductionOrder(recipe_id=recipe.id, line_id=line.id, status="tamamlandi", scheduled_qty_units=1000)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    submit_physical_tests(
        db_session, order,
        [{"test_type": "kalinlik", "value": 40.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None}],
    )
    new_version = db_session.query(Recipe).filter_by(parent_recipe_id=recipe.id).one()

    events = build_lifecycle_timeline(db_session, new_version.id)
    types = [e["event_type"] for e in events]
    assert types.count("recete_uretildi") == 1
    assert types.count("recete_revize_edildi") == 1


def test_regulation_change_event_uses_real_changed_at(db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)

    reg = Regulation(code="PPWR-ART-99", title="Test Madde", category="test", description="d")
    db_session.add(reg)
    db_session.flush()
    from datetime import datetime, timezone
    changed_at = datetime(2026, 1, 15, tzinfo=timezone.utc)
    db_session.add(
        RegulationRequirement(
            regulation_id=reg.id, regulation_no="EU 1", article="Md.1", requirement_text="t",
            version="2.0", previous_version="1.0", changed_at=changed_at, change_summary="Eşik %10'dan %20'ye çıktı.",
        )
    )
    db_session.add(
        RegulatoryAssessment(
            packaging_request_id=recipe.packaging_request_id, regulation_id=reg.id,
            verdict="uygun_gorunuyor", reasoning="t", regulation_version_snapshot="1.0",
        )
    )
    db_session.commit()

    events = build_lifecycle_timeline(db_session, recipe.id)
    reg_events = [e for e in events if e["event_type"] == "mevzuat_guncellendi"]
    assert len(reg_events) == 1
    assert reg_events[0]["detay"]["eski_versiyon"] == "1.0"
    assert reg_events[0]["detay"]["yeni_versiyon"] == "2.0"
    # SQLite zaman damgasını naive olarak geri döndürür -- tarih/saat
    # bileşenlerini karşılaştır, tzinfo'yu değil.
    assert reg_events[0]["tarih"].replace(tzinfo=timezone.utc) == changed_at


def test_http_lifecycle_timeline_endpoint(client, db_session):
    line = _line(db_session)
    material = _material(db_session)
    recipe = _recipe(db_session, line, material)

    resp = client.get(f"/api/v1/traceability/recipes/{recipe.id}/lifecycle-timeline")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert any(e["event_type"] == "sartname_olusturuldu" for e in body)


def test_http_lifecycle_timeline_404_for_unknown_recipe(client):
    resp = client.get("/api/v1/traceability/recipes/olmayan-id/lifecycle-timeline")
    assert resp.status_code == 404
