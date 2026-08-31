"""Faz H.5 — Optimizasyon Raporu'nun HİÇBİR bölümünde kaynağı belirsiz/boş
bir sayı kalmamasını garanti eden `report_source_label()` ve bunu kullanan
bölümlerin (`referans_recete`, `secilen_recete`, `tahmini_sonuclar`,
`iklim_dongusellik`) testleri. Kaynak gerçekten belirlenemiyorsa HER ZAMAN
"Veri Yok" döner -- ASLA rastgele bir kaynak uydurulmaz."""
import pytest

from app.models.knowledge import Material, Polymer
from app.models.production import SustainabilityResult
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer, RecipeMetric
from app.services import pdf_service
from app.services.report_service import build_optimization_report_data, report_source_label


# --- report_source_label(): saf fonksiyon testleri --------------------------

def test_none_returns_veri_yok():
    assert report_source_label(None) == "Veri Yok"


def test_unrecognized_string_returns_veri_yok():
    assert report_source_label("uydurma_bir_kaynak_xyz") == "Veri Yok"


def test_carbon_ef_tanimlanmadi_returns_veri_yok_not_varsayimsal():
    """'tanimlanmadi' -- kaynağı GERÇEKTEN bilinmeyen bir EF -- 'Varsayımsal'
    bile denilemez, dürüstçe 'Veri Yok' kalmalı."""
    assert report_source_label("tanimlanmadi") == "Veri Yok"


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("firma_verisi", "Firma Verisi"),
        ("gecmis_uretim", "Geçmiş Üretim"),
        ("makineden_alinan", "Makineden Alınan"),
        ("simulasyon", "Simülasyon"),
        ("teknik_veri_foyu", "Teknik Veri Föyü"),
        ("laboratuvar", "Laboratuvar"),
        ("mevzuat", "Mevzuat"),
        ("hesaplanan", "Hesaplanan"),
        ("sistem_referansi", "Sistem Referansı"),
        ("varsayimsal", "Varsayımsal"),
    ],
)
def test_canonical_10_word_vocabulary(kind, expected):
    assert report_source_label(kind) == expected


@pytest.mark.parametrize(
    "raw_signal,expected",
    [
        ("gecmis_uretim_verisi", "Geçmiş Üretim"),  # DataSourceType takma adı
        ("simulasyon_verisi", "Simülasyon"),
        ("laboratuvar_testi", "Laboratuvar"),
        ("kullanici_girisi", "Firma Verisi"),
        ("tanimli_gercek", "Sistem Referansı"),  # carbon_ef_status takma adı
        ("tanimli_demo", "Varsayımsal"),
    ],
)
def test_existing_signal_aliases_bridge_correctly(raw_signal, expected):
    assert report_source_label(raw_signal) == expected


# --- Rapor bölümlerinin _kaynak alanları -------------------------------------

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


def _verified_recipe(db, material, packaging_type="esnek film ambalaj", version=1, thickness=70.0):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test ürün", target_market="AB",
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
    db.add(
        RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=thickness)
    )
    db.commit()
    db.refresh(recipe)
    return recipe


def _add_sustainability_result(db, recipe, **overrides):
    per_1000 = {
        "virgin_kg": 10.0, "pcr_kg": 2.0, "regranul_kg": 0.0, "karbon_kg_co2": 20.0,
        "karbon_veri_kalitesi": "tanimli_demo", "fire_kg": 1.0, "enerji_kwh": 5.0,
    }
    per_1000.update(overrides)
    db.add(SustainabilityResult(recipe_id=recipe.id, per_1000_units=per_1000, is_actual=True))
    db.commit()


def _add_metrics(db, recipe, virgin_pct=100.0, pcr_pct=0.0, regranul_pct=0.0, carbon=1.8, cost=30.0):
    for metric_type, value, unit in [
        ("virgin_kullanimi", virgin_pct, "%"), ("pcr_kullanimi", pcr_pct, "%"),
        ("regranul_kullanimi", regranul_pct, "%"), ("karbon", carbon, "kg_co2/kg"), ("maliyet", cost, "TL/kg"),
    ]:
        db.add(RecipeMetric(recipe_id=recipe.id, metric_type=metric_type, value=value, unit=unit, is_estimated=True, data_source_type="hesaplanan"))
    db.commit()


def test_selected_recipe_and_tahmini_sections_carry_hesaplanan(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["secilen_recete"]["_kaynak"] == "Hesaplanan"
    assert data["tahmini_sonuclar"]["_kaynak"] == "Hesaplanan"
    assert data["iklim_dongusellik"]["_kaynak_kompozisyon"] == "Hesaplanan"


def test_reference_section_kaynak_none_when_no_reference(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["referans_recete"]["has_reference"] is False
    assert data["referans_recete"]["_kaynak"] is None


def test_reference_section_kaynak_gecmis_uretim_when_reference_exists(db_session):
    material = _material(db_session)
    old_recipe = _verified_recipe(db_session, material, version=1)
    _add_metrics(db_session, old_recipe)
    _add_sustainability_result(db_session, old_recipe)

    new_recipe = _verified_recipe(db_session, material, version=2)
    _add_metrics(db_session, new_recipe)
    _add_sustainability_result(db_session, new_recipe)

    data = build_optimization_report_data(db_session, new_recipe.id)

    assert data["referans_recete"]["has_reference"] is True
    assert data["referans_recete"]["_kaynak"] == "Geçmiş Üretim"


def test_climate_fire_enerji_kaynak_reflects_real_source_not_fabricated(db_session):
    """Faz H.3'ün `fire_enerji_veri_kaynagi`si SustainabilityResult'ta yoksa
    (ör. eski/manuel bir kayıt) '_kaynak_fire_enerji' dürüstçe 'Veri Yok'
    kalmalı -- uydurulmamalı."""
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)  # fire_enerji_veri_kaynagi YOK

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["iklim_dongusellik"]["_kaynak_fire_enerji"] == "Veri Yok"


def test_climate_fire_enerji_kaynak_shows_simulasyon_when_present(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe, fire_enerji_veri_kaynagi="simulasyon_verisi")

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["iklim_dongusellik"]["_kaynak_fire_enerji"] == "Simülasyon"


def test_pdf_renders_without_crash_with_new_source_fields(db_session):
    material = _material(db_session)
    old_recipe = _verified_recipe(db_session, material, version=1)
    _add_metrics(db_session, old_recipe)
    _add_sustainability_result(db_session, old_recipe)

    new_recipe = _verified_recipe(db_session, material, version=2)
    _add_metrics(db_session, new_recipe)
    _add_sustainability_result(db_session, new_recipe, fire_enerji_veri_kaynagi="simulasyon_verisi")

    data = build_optimization_report_data(db_session, new_recipe.id)
    pdf_bytes = pdf_service.render_technical_report(data, passport=None)
    assert len(pdf_bytes) > 1000
