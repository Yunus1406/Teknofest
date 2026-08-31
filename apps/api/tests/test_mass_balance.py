"""Kütle dengesi testleri — kullanıcı tarafından bildirilen somut senaryo:
400x300mm, 70 mikron PE film, yoğunluk ~920 kg/m3, iki yüzeyli (esnek film
ambalaj) -> tek ambalaj ~15.5g, 1000 ambalaj ~15.5 kg olmalı (önceki hatalı
hesap ~1000 kg gösteriyordu — 2 büyüklük mertebesi yanlıştı)."""
from types import SimpleNamespace

import pytest

from app.services.mass_balance import compute_mass_breakdown, compute_unit_mass_kg, weighted_density_kg_m3


def _material(density_g_cm3, material_type="virgin", carbon=1.8):
    return SimpleNamespace(
        density_g_cm3=density_g_cm3, material_type=material_type, carbon_factor_kg_co2_per_kg=carbon
    )


def _layer(layer_index, material, ratio_pct, thickness_micron):
    return SimpleNamespace(
        layer_index=layer_index, material=material, ratio_pct=ratio_pct, thickness_micron=thickness_micron
    )


def _recipe(layers, total_micron):
    return SimpleNamespace(layers=layers, total_micron=total_micron)


def test_single_layer_film_matches_hand_calculation():
    pe = _material(density_g_cm3=0.92)  # g/cm3 == 920 kg/m3
    recipe = _recipe([_layer(0, pe, 100.0, 70.0)], total_micron=70.0)

    unit_mass_kg = compute_unit_mass_kg(
        recipe, length_mm=400, width_mm=300, canonical_category="esnek_film_ambalaj"
    )

    assert unit_mass_kg is not None
    assert unit_mass_kg == pytest.approx(0.0155, rel=0.01)  # ~15.5 g/ambalaj


def test_mass_breakdown_per_1000_units_matches_expected_order_of_magnitude():
    pe = _material(density_g_cm3=0.92)
    recipe = _recipe([_layer(0, pe, 100.0, 70.0)], total_micron=70.0)

    breakdown = compute_mass_breakdown(
        recipe, length_mm=400, width_mm=300, canonical_category="esnek_film_ambalaj", unit_count=1000
    )

    assert breakdown is not None
    assert breakdown.total_mass_kg == pytest.approx(15.5, rel=0.02)
    assert breakdown.virgin_kg == pytest.approx(15.5, rel=0.02)
    # Eski hatalı hesap ~1000 kg (2 büyüklük mertebesi fazla) veriyordu.
    assert breakdown.total_mass_kg < 100


def test_single_sided_category_is_half_of_double_sided():
    pe = _material(density_g_cm3=0.92)
    recipe = _recipe([_layer(0, pe, 100.0, 70.0)], total_micron=70.0)

    single_sided = compute_unit_mass_kg(recipe, 400, 300, "plastik_tabak")
    double_sided = compute_unit_mass_kg(recipe, 400, 300, "esnek_film_ambalaj")

    assert double_sided == pytest.approx(single_sided * 2, rel=1e-6)


def test_multi_layer_blend_mass_split_by_material_type():
    virgin = _material(density_g_cm3=0.92, material_type="virgin", carbon=1.8)
    pcr = _material(density_g_cm3=0.92, material_type="pcr", carbon=0.6)
    layers = [
        _layer(0, virgin, 80.0, 70.0),
        _layer(0, pcr, 20.0, 70.0),
    ]
    recipe = _recipe(layers, total_micron=70.0)

    breakdown = compute_mass_breakdown(recipe, 400, 300, "esnek_film_ambalaj", unit_count=1000)

    assert breakdown is not None
    assert breakdown.virgin_kg == pytest.approx(breakdown.total_mass_kg * 0.8, rel=1e-6)
    assert breakdown.pcr_kg == pytest.approx(breakdown.total_mass_kg * 0.2, rel=1e-6)
    assert breakdown.virgin_kg + breakdown.pcr_kg == pytest.approx(breakdown.total_mass_kg, rel=1e-6)


def test_missing_dimensions_returns_none_instead_of_fabricating():
    pe = _material(density_g_cm3=0.92)
    recipe = _recipe([_layer(0, pe, 100.0, 70.0)], total_micron=70.0)
    assert compute_unit_mass_kg(recipe, None, None, "esnek_film_ambalaj") is None
    assert compute_mass_breakdown(recipe, None, None, "esnek_film_ambalaj", 1000) is None


def test_weighted_density_ignores_rows_with_unknown_density():
    known = _material(density_g_cm3=1.0)
    unknown = _material(density_g_cm3=None)
    layers = [_layer(0, known, 50.0, 100.0), _layer(0, unknown, 50.0, 100.0)]
    recipe = _recipe(layers, total_micron=100.0)
    # Sadece bilinen yoğunluklu satır üzerinden normalize edilmeli -> 1000 kg/m3
    assert weighted_density_kg_m3(recipe) == pytest.approx(1000.0, rel=1e-6)


def test_mass_breakdown_carbon_ef_status_is_undefined_for_legacy_mocks():
    """SimpleNamespace mock'ları `.carbon_ef` taşımaz -> resolve_carbon_ef
    dürüstçe 'tanimlanmadi' döner (bkz. app/services/carbon.py); rakamsal
    sonuç (carbon_kg_co2) yine de legacy carbon_factor_kg_co2_per_kg
    üzerinden doğru hesaplanmaya devam eder."""
    pe = _material(density_g_cm3=0.92, carbon=1.8)
    recipe = _recipe([_layer(0, pe, 100.0, 70.0)], total_micron=70.0)

    breakdown = compute_mass_breakdown(recipe, 400, 300, "esnek_film_ambalaj", unit_count=1000)

    assert breakdown.carbon_ef_status == "tanimlanmadi"
    assert breakdown.carbon_kg_co2 > 0  # arithmetik çökmedi, legacy değere düştü
