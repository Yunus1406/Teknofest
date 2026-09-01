"""Faz N.2 (Madde 15) — Rapor + Aşama 12 "Sektöre Göre Konum". Benchmark
verisi girilmemişse `available: False` ("Veri Yok"), asla bir sektör
ortalaması sentezlenmez/enterpole edilmez. Girilmişse reçetenin GERÇEK
(comparison["recommended"]) değeriyle kıyaslanır."""
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.company import Company, CompanyBenchmark
from app.models.knowledge import Material, Polymer
from app.models.production import PhysicalTest
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer, RecipeMetric
from app.services.pdf_service import render_technical_report
from app.services.report_service import build_optimization_report_data


def _client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def _material(db):
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    material = Material(
        polymer_id=polymer.id, name="Test Malzeme N2.3", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(material)
    db.flush()
    return material


def _verified_recipe(db, packaging_type="Plastik Tabak"):
    material = _material(db)
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, source="sistem_uretti", status="dogrulandi",
        is_verified=True, total_micron=70.0,
    )
    db.add(recipe)
    db.flush()
    db.add(
        RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0)
    )
    for metric_type, value, unit in [
        ("virgin_kullanimi", 100.0, "%"), ("pcr_kullanimi", 20.0, "%"),
        ("regranul_kullanimi", 0.0, "%"), ("karbon", 2.0, "kg_co2/kg"), ("maliyet", 25.0, "TL/kg"),
    ]:
        db.add(RecipeMetric(recipe_id=recipe.id, metric_type=metric_type, value=value, unit=unit, is_estimated=True, data_source_type="hesaplanan"))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_no_company_means_no_benchmark_data(db_session):
    recipe = _verified_recipe(db_session)
    data = build_optimization_report_data(db_session, recipe.id)
    assert data["sektore_gore_konum"] == {"available": False}


def test_company_without_matching_benchmark_row_means_no_data(db_session):
    db_session.add(Company(name="Test Firma N2.3"))
    db_session.commit()
    recipe = _verified_recipe(db_session)

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["sektore_gore_konum"]["available"] is False
    assert data["sektore_gore_konum"]["packaging_category"] == "plastik_tabak"


def test_matching_benchmark_row_produces_real_comparison(db_session):
    company = Company(name="Test Firma N2.3b")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    db_session.add(
        CompanyBenchmark(
            company_id=company.id, packaging_category="plastik_tabak", metric_name="karbon_kg_co2_per_kg",
            value=2.5, unit="kg CO2/kg", source="Kendi 2025 üretim ortalamamız",
        )
    )
    db_session.commit()
    recipe = _verified_recipe(db_session)

    data = build_optimization_report_data(db_session, recipe.id)
    section = data["sektore_gore_konum"]

    assert section["available"] is True
    assert section["packaging_category"] == "plastik_tabak"
    assert len(section["items"]) == 1
    item = section["items"][0]
    assert item["metric_name"] == "karbon_kg_co2_per_kg"
    assert item["benchmark_value"] == 2.5
    assert item["benchmark_source"] == "Kendi 2025 üretim ortalamamız"
    # Reçetenin GERÇEK karbon değeri (RecipeMetric "karbon"=2.0) benchmark
    # (2.5) ile kıyaslanır -- ikisi de gerçek veri, hiçbiri uydurulmadı.
    assert item["recete_degeri"] == 2.0
    assert item["fark_pct"] == -20.0


def test_benchmark_row_for_different_category_is_not_matched(db_session):
    company = Company(name="Test Firma N2.3c")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    db_session.add(
        CompanyBenchmark(
            company_id=company.id, packaging_category="sise", metric_name="karbon_kg_co2_per_kg",
            value=2.5, unit="kg CO2/kg", source="test",
        )
    )
    db_session.commit()
    recipe = _verified_recipe(db_session, packaging_type="Plastik Tabak")

    data = build_optimization_report_data(db_session, recipe.id)
    assert data["sektore_gore_konum"]["available"] is False


def test_pdf_renders_with_benchmark_comparison_present(db_session):
    company = Company(name="Test Firma N2.3d")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    db_session.add(
        CompanyBenchmark(
            company_id=company.id, packaging_category="plastik_tabak", metric_name="maliyet_tl_per_kg",
            value=30.0, unit="TL/kg", source="test",
        )
    )
    db_session.commit()
    recipe = _verified_recipe(db_session)

    data = build_optimization_report_data(db_session, recipe.id)
    pdf_bytes = render_technical_report(data)
    assert pdf_bytes[:5] == b"%PDF-"


def test_finalize_result_http_includes_benchmark_field_when_no_data(db_session):
    recipe = _verified_recipe(db_session)
    db_session.add(
        PhysicalTest(recipe_id=recipe.id, test_type="kalinlik", value=70.0, unit="mikron", result="basarili")
    )
    db_session.commit()
    client = _client(db_session)
    try:
        resp = client.post(f"/api/v1/production-flow/recipes/{recipe.id}/finalize")
        assert resp.status_code == 200, resp.text
        assert resp.json()["benchmark_karsilastirmasi"] == {"available": False}
    finally:
        app.dependency_overrides.clear()


def test_finalize_result_http_includes_real_benchmark_comparison(db_session):
    company = Company(name="Test Firma N2.3e")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    db_session.add(
        CompanyBenchmark(
            company_id=company.id, packaging_category="plastik_tabak", metric_name="karbon_kg_co2_per_kg",
            value=2.5, unit="kg CO2/kg", source="Kendi 2025 üretim ortalamamız",
        )
    )
    recipe = _verified_recipe(db_session)
    db_session.add(
        PhysicalTest(recipe_id=recipe.id, test_type="kalinlik", value=70.0, unit="mikron", result="basarili")
    )
    db_session.commit()
    client = _client(db_session)
    try:
        resp = client.post(f"/api/v1/production-flow/recipes/{recipe.id}/finalize")
        assert resp.status_code == 200, resp.text
        benchmark = resp.json()["benchmark_karsilastirmasi"]
        assert benchmark["available"] is True
        assert benchmark["items"][0]["benchmark_value"] == 2.5
    finally:
        app.dependency_overrides.clear()
