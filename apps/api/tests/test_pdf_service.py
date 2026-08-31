"""Faz C.6 — PDF üretimi. `render_technical_report`/`render_executive_
summary`'nin gerçek bir PDF ürettiğini (magic bytes), referanssız
senaryoda Yönetici Özeti'nde uydurma bir `%` göstermediğini, eksik/boş
veride (fiziksel test yok, üretim emri yok) çökmediğini ve QR'ın SADECE
gerçek bir pasaport verildiğinde eklendiğini doğrular."""
import pytest

from app.models.knowledge import Material, Polymer
from app.models.production import SustainabilityResult
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.pdf_service import render_executive_summary, render_technical_report
from app.services.report_service import build_optimization_report_data


def _material(db):
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


def _minimal_report_data(db):
    """Fiziksel test yok, üretim emri yok, referans yok -- en 'boş' senaryo.
    PDF render'ının bu durumda ÇÖKMEMESİ bu testin asıl amacı."""
    material = _material(db)
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, source="referans_receteden", status="dogrulandi",
        is_verified=True, total_micron=70.0,
    )
    db.add(recipe)
    db.flush()
    db.add(
        RecipeLayer(
            recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id,
            ratio_pct=100.0, thickness_micron=70.0,
        )
    )
    db.commit()
    db.refresh(recipe)
    return build_optimization_report_data(db, recipe.id)


def _report_data_with_sustainability(db):
    material = _material(db)
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
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
        RecipeLayer(
            recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id,
            ratio_pct=100.0, thickness_micron=70.0,
        )
    )
    db.add(
        SustainabilityResult(
            recipe_id=recipe.id,
            per_1000_units={
                "virgin_kg": 10.0, "pcr_kg": 2.0, "regranul_kg": 0.0, "karbon_kg_co2": 20.0,
                "karbon_veri_kalitesi": "tanimli_demo", "fire_kg": 1.0, "enerji_kwh": 5.0,
            },
            is_actual=True,
        )
    )
    db.commit()
    db.refresh(recipe)
    return build_optimization_report_data(db, recipe.id)


def test_technical_report_produces_valid_pdf_bytes(db_session):
    data = _report_data_with_sustainability(db_session)
    pdf_bytes = render_technical_report(data)
    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 500


def test_executive_summary_produces_valid_pdf_bytes(db_session):
    data = _report_data_with_sustainability(db_session)
    pdf_bytes = render_executive_summary(data)
    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 500


def test_executive_summary_shows_no_percentage_when_no_reference(db_session):
    """Faz A kuralı: referans yoksa % azaltım gösterilmez -- PDF metninde
    de bu doğru yansımalı (mutlak rakamlar, hesaplanmış bir % değil)."""
    data = _report_data_with_sustainability(db_session)
    assert data["yonetici_ozeti"]["has_reference"] is False

    pdf_bytes = render_executive_summary(data)
    from pypdf import PdfReader
    from io import BytesIO
    text = PdfReader(BytesIO(pdf_bytes)).pages[0].extract_text()

    assert "hesaplanmadı" in text
    assert "10.0" in text or "10,0" in text  # gerçekleşen mutlak virgin_kg değeri


def test_rendering_does_not_crash_on_minimal_empty_data(db_session):
    """Fiziksel test yok, üretim emri yok, referans yok, sürdürülebilirlik
    verisi yok -- en boş senaryoda bile render çökmemeli."""
    data = _minimal_report_data(db_session)

    technical = render_technical_report(data)
    executive = render_executive_summary(data)

    assert technical[:5] == b"%PDF-"
    assert executive[:5] == b"%PDF-"


def test_qr_page_added_only_when_passport_provided(db_session):
    data = _report_data_with_sustainability(db_session)

    without_passport = render_technical_report(data, passport=None)

    from pypdf import PdfReader
    from io import BytesIO
    pages_without = len(PdfReader(BytesIO(without_passport)).pages)

    fake_passport = {
        "passport_no": "DPP-2026-000099",
        "qr_code_data_uri": _tiny_png_data_uri(),
    }
    with_passport = render_technical_report(data, passport=fake_passport)
    pages_with = len(PdfReader(BytesIO(with_passport)).pages)

    assert pages_with > pages_without


def test_no_qr_block_when_passport_missing_fields(db_session):
    data = _report_data_with_sustainability(db_session)

    without_passport = render_technical_report(data, passport=None)
    without_passport2 = render_technical_report(data, passport={})

    from pypdf import PdfReader
    from io import BytesIO
    assert len(PdfReader(BytesIO(without_passport)).pages) == len(PdfReader(BytesIO(without_passport2)).pages)


def _tiny_png_data_uri() -> str:
    import qrcode
    import base64
    from io import BytesIO

    img = qrcode.make("https://example.invalid/dpp/DPP-2026-000099")
    buf = BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
