"""Faz I.4 — Sistem Geneli "Veri Güveni" Etiketlemesi. `data_confidence_
level()` H.5'in kaynak etiketinden TÜRETİLİR (ayrı bir hesaplama değil) --
aynı `kind` girdi kümesini 4 kademeli Yüksek/Orta/Düşük/Varsayımsal
ölçeğine çevirir. Kaynak gerçekten belirlenemiyorsa rozet hiç gösterilmez
(None döner)."""
import pytest

from app.models.knowledge import Material, Polymer
from app.models.production import SustainabilityResult
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer, RecipeMetric
from app.services import pdf_service
from app.services.report_service import build_optimization_report_data, data_confidence_level


def test_none_returns_none():
    assert data_confidence_level(None) is None


def test_unrecognized_string_returns_none():
    assert data_confidence_level("uydurma_bir_kaynak_xyz") is None


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("makineden_alinan", "Yüksek"),
        ("laboratuvar", "Yüksek"),
        ("firma_verisi", "Yüksek"),
        ("laboratuvar_testi", "Yüksek"),
        ("kullanici_girisi", "Yüksek"),
        ("gecmis_uretim", "Orta"),
        ("teknik_veri_foyu", "Orta"),
        ("hesaplanan", "Orta"),
        ("gecmis_uretim_verisi", "Orta"),
        ("mevzuat", "Düşük"),
        ("sistem_referansi", "Düşük"),
        ("simulasyon", "Düşük"),
        ("simulasyon_verisi", "Düşük"),
        ("tanimli_gercek", "Düşük"),
        ("varsayimsal", "Varsayımsal"),
        ("tanimli_demo", "Varsayımsal"),
    ],
)
def test_confidence_scale(kind, expected):
    assert data_confidence_level(kind) == expected


def test_tanimlanmadi_returns_none_not_a_level():
    """'tanımlanmadı' -- kaynağı GERÇEKTEN bilinmeyen -- hiçbir güven
    seviyesine düşmemeli, rozet hiç gösterilmemeli."""
    assert data_confidence_level("tanimlanmadi") is None


# --- Rapor bölümlerinin _guven alanları --------------------------------------

def _material(db, name="Test Malzeme"):
    polymer = db.query(Polymer).filter_by(code="PE").one_or_none()
    if polymer is None:
        polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
        db.add(polymer)
        db.flush()
    material = Material(
        polymer_id=polymer.id, name=name, material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(material)
    db.flush()
    return material


def _verified_recipe(db, material, version=1, thickness=70.0):
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=version, source="sistem_uretti", status="dogrulandi",
        is_verified=True, total_micron=thickness,
    )
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=thickness))
    db.commit()
    db.refresh(recipe)
    return recipe


def _add_sustainability_result(db, recipe, **overrides):
    per_1000 = {
        "virgin_kg": 10.0, "pcr_kg": 2.0, "regranul_kg": 0.0, "karbon_kg_co2": 20.0,
        "karbon_veri_kalitesi": "tanimli_demo", "fire_kg": 1.0, "enerji_kwh": 5.0,
        "kutle_veri_kaynagi": "hesaplanan", "fire_enerji_veri_kaynagi": "simulasyon_verisi",
    }
    per_1000.update(overrides)
    db.add(SustainabilityResult(recipe_id=recipe.id, per_1000_units=per_1000, is_actual=True))
    db.commit()


def _add_metrics(db, recipe):
    for metric_type, value, unit in [
        ("virgin_kullanimi", 100.0, "%"), ("pcr_kullanimi", 0.0, "%"),
        ("regranul_kullanimi", 0.0, "%"), ("karbon", 1.8, "kg_co2/kg"), ("maliyet", 30.0, "TL/kg"),
    ]:
        db.add(RecipeMetric(recipe_id=recipe.id, metric_type=metric_type, value=value, unit=unit, is_estimated=True, data_source_type="hesaplanan"))
    db.commit()


def test_selected_recipe_and_tahmini_sections_carry_orta_guven(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["secilen_recete"]["_guven"] == "Orta"  # hesaplanan
    assert data["tahmini_sonuclar"]["_guven"] == "Orta"
    assert data["iklim_dongusellik"]["_guven_kompozisyon"] == "Orta"
    assert data["iklim_dongusellik"]["_guven_fire_enerji"] == "Düşük"  # simulasyon_verisi


def test_reference_section_guven_none_when_no_reference(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["referans_recete"]["_guven"] is None


def test_reference_section_guven_orta_when_reference_exists(db_session):
    material = _material(db_session)
    old_recipe = _verified_recipe(db_session, material, version=1)
    _add_metrics(db_session, old_recipe)
    _add_sustainability_result(db_session, old_recipe)

    new_recipe = _verified_recipe(db_session, material, version=2)
    _add_metrics(db_session, new_recipe)
    _add_sustainability_result(db_session, new_recipe)

    data = build_optimization_report_data(db_session, new_recipe.id)

    assert data["referans_recete"]["_guven"] == "Orta"  # gecmis_uretim


def test_source_matrix_carries_guven_column(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    matrix = data["veri_kaynagi_matrisi"]
    assert len(matrix) > 0
    assert all("guven" in row for row in matrix)


def test_pdf_renders_with_confidence_lines_without_crash(db_session):
    material = _material(db_session)
    old_recipe = _verified_recipe(db_session, material, version=1)
    _add_metrics(db_session, old_recipe)
    _add_sustainability_result(db_session, old_recipe)

    new_recipe = _verified_recipe(db_session, material, version=2)
    _add_metrics(db_session, new_recipe)
    _add_sustainability_result(db_session, new_recipe, fire_enerji_veri_kaynagi="simulasyon_verisi")

    data = build_optimization_report_data(db_session, new_recipe.id)
    pdf_bytes = pdf_service.render_technical_report(data, passport=None)

    assert pdf_bytes[:5] == b"%PDF-"
    from io import BytesIO
    from pypdf import PdfReader
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(pdf_bytes)).pages)
    assert "Veri Güveni" in text
