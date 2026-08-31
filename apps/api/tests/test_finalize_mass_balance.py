"""Aşama 12 (finalize_result) uçtan uca kütle dengesi entegrasyon testi —
gerçek ORM nesneleriyle, kullanıcının bildirdiği somut senaryoya göre."""
import pytest

from app.models.knowledge import Material, Polymer
from app.models.production import PhysicalTest
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.production_flow_service import finalize_result


def _seed_pe_film_recipe(db_session):
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()

    material = Material(
        polymer_id=polymer.id,
        name="PE Virgin Film Sınıfı",
        material_type="virgin",
        density_g_cm3=0.92,
        degradation_factor=0.0,
        food_contact_eligible=True,
        max_recommended_ratio_pct=100.0,
        cost_per_kg=34.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db_session.add(material)
    db_session.flush()

    request = PackagingRequest(
        packaging_type="esnek film ambalaj",
        usage_area="kuru gıda poşetleme",
        product="atıştırmalık poşeti",
        target_market="yurt içi",
        food_contact=True,
        target_volume_units=1000,
        dimensions={"length_mm": 400, "width_mm": 300},
    )
    db_session.add(request)
    db_session.flush()

    recipe = Recipe(
        packaging_request_id=request.id,
        version=1,
        source="sistem_uretti",
        status="onerildi",
        total_micron=70.0,
    )
    db_session.add(recipe)
    db_session.flush()
    db_session.add(
        RecipeLayer(
            recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id,
            ratio_pct=100.0, thickness_micron=70.0,
        )
    )
    # Faz D.2 — finalize_result artık en az bir gerçekten BAŞARILI fiziksel
    # test kaydı olmadan reddediyor (bkz. production_flow_service.py).
    db_session.add(
        PhysicalTest(
            recipe_id=recipe.id, test_type="kalinlik", value=70.0, unit="mikron",
            target_min=63.0, target_max=77.0, result="basarili", passed=True,
        )
    )
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


def test_finalize_result_produces_physically_plausible_mass(db_session):
    recipe = _seed_pe_film_recipe(db_session)

    result = finalize_result(db_session, recipe)

    per_1000 = result.per_1000_units
    assert per_1000["virgin_kg"] == pytest.approx(15.5, rel=0.02)
    # Eski hata ~1000 kg (2 büyüklük mertebesi fazla) döndürüyordu.
    assert per_1000["virgin_kg"] < 100
    assert per_1000["pcr_kg"] == pytest.approx(0.0, abs=1e-6)
    assert recipe.is_verified is True


def test_finalize_result_without_dimensions_does_not_fabricate_mass(db_session):
    recipe = _seed_pe_film_recipe(db_session)
    recipe.packaging_request.dimensions = {}
    db_session.commit()

    result = finalize_result(db_session, recipe)

    assert result.per_1000_units["virgin_kg"] is None
    assert "_uyari" in result.per_1000_units
