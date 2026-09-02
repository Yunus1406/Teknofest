"""Faz S.1 (Madde 29) — QR Kodla Geri Dönüşüm Yönlendirmesi. `geri_donusum_
rehberi` her zaman DPP'nin public (tüketici) görünümünde olmalı; tek/çoklu
polimer durumları dürüstçe ayrışmalı, hiçbir gerçek/uydurma URL üretilmemeli."""
import pytest

from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.passport_service import build_passport_content, get_or_create_passport
from app.services.recycling_guidance_service import build_recycling_guidance


def _polymer(db, code):
    p = db.query(Polymer).filter_by(code=code).one_or_none()
    if p is None:
        p = Polymer(code=code, name=code, category="poliolefin", base_properties={})
        db.add(p)
        db.flush()
    return p


def _material(db, polymer_code):
    polymer = _polymer(db, polymer_code)
    m = Material(
        polymer_id=polymer.id, name=f"Test {polymer_code}", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(m)
    db.flush()
    return m


def _recipe_with_materials(db, materials):
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(packaging_request_id=req.id, version=1, source="sistem_uretti", status="dogrulandi", is_verified=True, total_micron=70.0)
    db.add(recipe)
    db.flush()
    for i, m in enumerate(materials):
        db.add(RecipeLayer(recipe_id=recipe.id, layer_index=i, layer_label=chr(65 + i), material_id=m.id, ratio_pct=100.0 / len(materials), thickness_micron=70.0 / len(materials)))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_single_known_polymer_gives_specific_instruction(db_session):
    material = _material(db_session, "PE")
    recipe = _recipe_with_materials(db_session, [material])

    guidance = build_recycling_guidance(recipe)

    assert "PE" in guidance["malzeme_aciklamasi"]
    assert "Plastik geri dönüşüm kutusu" in guidance["kutu_talimati"]
    assert "sertifikasyonu" in guidance["aciklama"]


def test_single_unknown_polymer_is_honestly_flagged(db_session):
    material = _material(db_session, "EVOH")
    recipe = _recipe_with_materials(db_session, [material])

    guidance = build_recycling_guidance(recipe)

    assert "tanımlı değil" in guidance["kutu_talimati"]


def test_multi_material_structure_gives_honest_mixed_note(db_session):
    m1 = _material(db_session, "PE")
    m2 = _material(db_session, "EVOH")
    recipe = _recipe_with_materials(db_session, [m1, m2])

    guidance = build_recycling_guidance(recipe)

    assert "çok katmanlı" in guidance["kutu_talimati"]
    assert "PE" in guidance["malzeme_aciklamasi"] and "EVOH" in guidance["malzeme_aciklamasi"]


def test_no_url_is_ever_generated(db_session):
    material = _material(db_session, "PET")
    recipe = _recipe_with_materials(db_session, [material])

    guidance = build_recycling_guidance(recipe)

    for value in guidance.values():
        assert "http://" not in value and "https://" not in value


def test_pla_gets_compost_not_plastic_bin_instruction(db_session):
    material = _material(db_session, "PLA")
    recipe = _recipe_with_materials(db_session, [material])

    guidance = build_recycling_guidance(recipe)

    assert "kompost" in guidance["kutu_talimati"].lower()


def test_recycling_guidance_is_always_in_public_passport_content(db_session):
    material = _material(db_session, "PP")
    recipe = _recipe_with_materials(db_session, [material])
    passport = get_or_create_passport(db_session, recipe.id)

    content = build_passport_content(db_session, passport, include_authorized=False)

    assert content["authorized"] is None
    rehber = content["public"]["geri_donusum_rehberi"]
    assert rehber["malzeme_aciklamasi"]
    assert rehber["kutu_talimati"]
    assert rehber["yerel_yonlendirme"]
    assert rehber["aciklama"]
