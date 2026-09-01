"""Faz O.2 (Madde 19) — Rapor'un 24. bölümü: Sürdürülebilirlik Karnesi.
Hiçbir sayı yeniden hesaplanmaz; `data["surdurulebilirlik_karnesi"]`
zaten hesaplanmış olarak render edilir. Referans yoksa "Referans yok"
yazılır -- ASLA uydurma bir karşılaştırma yüzdesi basılmaz."""
from io import BytesIO

from pypdf import PdfReader

from app.models.knowledge import Material, Polymer
from app.models.production import SustainabilityResult
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer, RecipeMetric
from app.services.pdf_service import render_technical_report
from app.services.report_service import build_optimization_report_data


def _material(db):
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    material = Material(
        polymer_id=polymer.id, name="Test Malzeme O2c", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(material)
    db.flush()
    return material


def _report_data(db):
    material = _material(db)
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test ürün", target_market="AB",
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
        ("virgin_kullanimi", 80.0, "%"), ("pcr_kullanimi", 20.0, "%"),
        ("regranul_kullanimi", 0.0, "%"), ("karbon", 1.8, "kg_co2/kg"), ("maliyet", 30.0, "TL/kg"),
    ]:
        db.add(RecipeMetric(recipe_id=recipe.id, metric_type=metric_type, value=value, unit=unit, is_estimated=True, data_source_type="hesaplanan"))
    db.add(
        SustainabilityResult(
            recipe_id=recipe.id,
            per_1000_units={
                "virgin_kg": 8.0, "pcr_kg": 2.0, "regranul_kg": 0.0, "karbon_kg_co2": 20.0,
                "karbon_veri_kalitesi": "tanimli_demo", "fire_kg": 1.0, "enerji_kwh": 5.0,
                "fire_enerji_veri_kaynagi": "simulasyon_verisi",
            },
            is_actual=True,
        )
    )
    db.commit()
    db.refresh(recipe)
    return build_optimization_report_data(db, recipe.id)


def test_report_data_includes_scorecard_key(db_session):
    data = _report_data(db_session)
    assert "surdurulebilirlik_karnesi" in data
    assert len(data["surdurulebilirlik_karnesi"]["dimensions"]) == 9


def test_pdf_renders_scorecard_section_without_crashing(db_session):
    data = _report_data(db_session)
    pdf_bytes = render_technical_report(data)
    assert pdf_bytes[:5] == b"%PDF-"

    text = "".join(page.extract_text() for page in PdfReader(BytesIO(pdf_bytes)).pages)
    assert "Sürdürülebilirlik Karnesi" in text
    assert "Referans yok" in text  # bu senaryoda referans reçete yok
    assert "Malzeme Verimliliği" in text
    assert "Kanıt Tamamlanma" in text
