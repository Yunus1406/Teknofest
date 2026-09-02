"""Faz T.1e (Madde 31) — DPP'nin Yetkili Alan'ına Üretim Öncesi Risk Skoru
(Faz Q.1/R.3), Kanıt Tamamlanma Oranı (Faz R.2, SKU-scoped) ve Benchmark
karşılaştırması (Faz N.2) eklendi. Hepsi REUSE, yeni hesaplama yok. SKU
yoksa kanıt tamamlanma dürüstçe None (uydurulmaz)."""
import pytest

from app.models.knowledge import Material, Polymer
from app.models.product_sku import ProductSku
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.passport_service import build_passport_content, get_or_create_passport
from app.services.risk_service import compute_risk_score


def _material(db):
    polymer = db.query(Polymer).filter_by(code="PE").one_or_none()
    if polymer is None:
        polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
        db.add(polymer)
        db.flush()
    m = Material(
        polymer_id=polymer.id, name="Test Malzeme", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(m)
    db.flush()
    return m


def _recipe(db, material, sku_id=None):
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={}, sku_id=sku_id,
    )
    db.add(req)
    db.flush()
    recipe = Recipe(packaging_request_id=req.id, version=1, source="sistem_uretti", status="dogrulandi", is_verified=True, total_micron=70.0)
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_risk_skoru_in_authorized_matches_service_exactly(db_session):
    material = _material(db_session)
    recipe = _recipe(db_session, material)
    passport = get_or_create_passport(db_session, recipe.id)

    content = build_passport_content(db_session, passport, include_authorized=True)

    expected = compute_risk_score(db_session, recipe)
    assert content["authorized"]["risk_skoru"] == expected


def test_kanit_tamamlanma_orani_none_without_sku(db_session):
    material = _material(db_session)
    recipe = _recipe(db_session, material, sku_id=None)
    passport = get_or_create_passport(db_session, recipe.id)

    content = build_passport_content(db_session, passport, include_authorized=True)

    assert content["authorized"]["kanit_tamamlanma_orani"] is None


def test_kanit_tamamlanma_orani_present_with_sku(db_session):
    material = _material(db_session)
    sku = ProductSku(sku_code="SKU-T1E", product_name="Test Ürün", packaging_type="esnek film ambalaj", usage_area="x", target_market="AB")
    db_session.add(sku)
    db_session.flush()
    recipe = _recipe(db_session, material, sku_id=sku.id)
    sku.current_recipe_id = recipe.id
    db_session.commit()
    passport = get_or_create_passport(db_session, recipe.id)

    content = build_passport_content(db_session, passport, include_authorized=True)

    kanit = content["authorized"]["kanit_tamamlanma_orani"]
    assert kanit is not None
    assert kanit["toplam"] == 11
    assert 0 <= kanit["tamam_sayisi"] <= 11


def test_sektore_gore_konum_honestly_unavailable_without_benchmark_data(db_session):
    material = _material(db_session)
    recipe = _recipe(db_session, material)
    passport = get_or_create_passport(db_session, recipe.id)

    content = build_passport_content(db_session, passport, include_authorized=True)

    assert content["authorized"]["sektore_gore_konum"]["available"] is False


def test_public_content_never_carries_authorized_only_fields(db_session):
    material = _material(db_session)
    recipe = _recipe(db_session, material)
    passport = get_or_create_passport(db_session, recipe.id)

    content = build_passport_content(db_session, passport, include_authorized=False)

    assert content["authorized"] is None
    assert "risk_skoru" not in content["public"]
