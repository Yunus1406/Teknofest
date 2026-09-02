"""Aşama 11 önerilen test hedefleri — reçeteden türetildiğini, sabit bir
şablon olmadığını doğrular (bkz. kullanıcı bildirimi: 70 µm reçete için
600 µm hedef görünmesi). Fonksiyon DB'ye dokunmaz, saf nesne öznitelikleri
üzerinden çalışır -> testler hafif SimpleNamespace nesneleriyle yazılmıştır."""
from types import SimpleNamespace

import pytest

from app.services.test_targets import suggested_physical_test_targets


def _recipe(total_micron: float, density_g_cm3: float = 0.92, carbon: float = 1.8):
    material = SimpleNamespace(density_g_cm3=density_g_cm3, material_type="virgin", carbon_factor_kg_co2_per_kg=carbon)
    layer = SimpleNamespace(layer_index=0, material=material, ratio_pct=100.0, thickness_micron=total_micron)
    return SimpleNamespace(layers=[layer], total_micron=total_micron)


def test_thickness_target_matches_actual_recipe_not_a_fixed_template():
    recipe = _recipe(total_micron=70.0)

    targets = suggested_physical_test_targets(recipe)
    kalinlik = next(t for t in targets if t.test_type == "kalinlik")

    assert kalinlik.nominal_value == 70.0
    assert kalinlik.target_min == pytest.approx(63.0)
    assert kalinlik.target_max == pytest.approx(77.0)
    # Eski sabit şablon 570-630 idi -- 70 mikronluk bir reçete için asla çıkmamalı.
    assert kalinlik.target_max < 570


def test_thickness_target_scales_with_a_different_recipe():
    """Aynı fonksiyon, 600 mikronluk bir tabak reçetesi için de doğru
    ölçekte hedef üretmeli (şablon sabit değil, reçeteye göre değişiyor)."""
    recipe = _recipe(total_micron=600.0, density_g_cm3=1.05, carbon=2.0)

    targets = suggested_physical_test_targets(recipe)
    kalinlik = next(t for t in targets if t.test_type == "kalinlik")
    assert kalinlik.nominal_value == 600.0
    assert kalinlik.target_min == pytest.approx(540.0)
    assert kalinlik.target_max == pytest.approx(660.0)


def test_gramaj_uses_area_density_unit_not_per_unit_weight():
    recipe = _recipe(total_micron=70.0)

    targets = suggested_physical_test_targets(recipe)
    gramaj = next(t for t in targets if t.test_type == "gramaj")
    assert gramaj.unit == "g/m²"
    # yoğunluk(kg/m3=920) * kalınlık(m=0.00007) * 1000 = 64.4 g/m2
    assert gramaj.nominal_value == pytest.approx(64.4, rel=0.02)


def test_mechanical_tests_never_fabricate_numeric_targets():
    recipe = _recipe(total_micron=70.0)

    targets = suggested_physical_test_targets(recipe)
    for t in targets:
        if t.test_type in ("tensile", "elongation", "dart_impact", "tear", "seal"):
            assert t.target_min is None
            assert t.target_max is None
            assert t.nominal_value is None
            assert t.test_method  # yöntem referansı yine de verilmeli
            assert t.target_source is None


# --- Mekanik Test Kabul Kriterleri (Aşama 2'de kullanıcı girişi) -----------

def test_user_criteria_becomes_real_target_not_just_a_suggestion():
    recipe = _recipe(total_micron=70.0)
    user_criteria = {"tensile": {"min": 25.0, "max": 40.0}}

    targets = suggested_physical_test_targets(recipe, user_criteria=user_criteria)
    tensile = next(t for t in targets if t.test_type == "tensile")

    assert tensile.target_min == 25.0
    assert tensile.target_max == 40.0
    assert tensile.target_source == "kullanici_girisi"
    assert "Aşama 2" in tensile.note


def test_user_criteria_with_only_min_still_applies():
    recipe = _recipe(total_micron=70.0)
    user_criteria = {"seal": {"min": 5.0, "max": None}}

    targets = suggested_physical_test_targets(recipe, user_criteria=user_criteria)
    seal = next(t for t in targets if t.test_type == "seal")

    assert seal.target_min == 5.0
    assert seal.target_max is None
    assert seal.target_source == "kullanici_girisi"


def test_untouched_mechanical_tests_keep_honest_manual_entry_note():
    """Kullanıcı sadece tensile'ı doldurduysa, diğer mekanik testler
    (ör. elongation) hâlâ dürüstçe 'elle girilmelidir' kalmalı -- kısmi
    kullanıcı girişi diğer testlere sızmamalı."""
    recipe = _recipe(total_micron=70.0)
    user_criteria = {"tensile": {"min": 25.0, "max": None}}

    targets = suggested_physical_test_targets(recipe, user_criteria=user_criteria)
    elongation = next(t for t in targets if t.test_type == "elongation")

    assert elongation.target_min is None
    assert elongation.target_max is None
    assert elongation.target_source is None
    assert "elle girilmelidir" in elongation.note


def test_thickness_and_gramaj_targets_are_tagged_as_calculated():
    recipe = _recipe(total_micron=70.0)

    targets = suggested_physical_test_targets(recipe)
    kalinlik = next(t for t in targets if t.test_type == "kalinlik")
    gramaj = next(t for t in targets if t.test_type == "gramaj")

    assert kalinlik.target_source == "hesaplanan"
    assert gramaj.target_source == "hesaplanan"


def test_no_user_criteria_preserves_existing_honest_behavior():
    """user_criteria hiç verilmezse (None) mevcut davranış birebir korunur
    -- geriye dönük uyumluluk."""
    recipe = _recipe(total_micron=70.0)

    targets = suggested_physical_test_targets(recipe, user_criteria=None)
    for t in targets:
        if t.test_type in ("tensile", "elongation", "dart_impact", "tear", "seal"):
            assert t.target_min is None
            assert t.target_source is None
