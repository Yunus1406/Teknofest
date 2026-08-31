"""Faz C.1 — Dijital Ürün Pasaportu veri modeli + kimlik/versiyon mantığı.
İçerik derleme (public/authorized ayrımı, QR) Faz C.2'de test edilecek."""
import re

import pytest

from app.models.digital_product_passport import DigitalProductPassport
from app.models.knowledge import Material, Polymer
from app.models.product_sku import ProductSku
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.passport_service import get_or_create_passport


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


def _verified_recipe(db, material, packaging_request_id, version=1):
    recipe = Recipe(
        packaging_request_id=packaging_request_id, version=version, source="sistem_uretti",
        status="dogrulandi", is_verified=True, total_micron=70.0,
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
    return recipe


def _packaging_request(db, sku_id=None):
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={}, sku_id=sku_id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_passport_no_format(db_session):
    material = _material(db_session)
    req = _packaging_request(db_session)
    recipe = _verified_recipe(db_session, material, req.id)

    passport = get_or_create_passport(db_session, recipe.id)

    assert re.fullmatch(r"DPP-\d{4}-\d{6}", passport.passport_no)
    assert passport.revision == 1
    assert passport.previous_passport_id is None


def test_unverified_recipe_is_rejected(db_session):
    material = _material(db_session)
    req = _packaging_request(db_session)
    recipe = Recipe(
        packaging_request_id=req.id, version=1, source="sistem_uretti",
        status="onerildi", is_verified=False,
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)

    with pytest.raises(ValueError, match="doğrulanmış"):
        get_or_create_passport(db_session, recipe.id)


def test_get_or_create_is_idempotent_for_same_recipe(db_session):
    material = _material(db_session)
    req = _packaging_request(db_session)
    recipe = _verified_recipe(db_session, material, req.id)

    first = get_or_create_passport(db_session, recipe.id)
    second = get_or_create_passport(db_session, recipe.id)

    assert first.id == second.id
    assert db_session.query(DigitalProductPassport).count() == 1


def test_revision_chain_for_same_sku(db_session):
    """Aynı SKU'ya bağlı iki farklı case (iki ayrı PackagingRequest, iki ayrı
    doğrulanmış reçete) -> ikinci pasaport revision=2, öncekine işaret eder."""
    material = _material(db_session)
    sku = ProductSku(
        sku_code="TST-001", product_name="Test Ürünü", packaging_type="esnek film ambalaj",
        usage_area="test", target_market="AB", food_contact=True, dimensions={},
    )
    db_session.add(sku)
    db_session.commit()
    db_session.refresh(sku)

    req1 = _packaging_request(db_session, sku_id=sku.id)
    recipe1 = _verified_recipe(db_session, material, req1.id)
    passport1 = get_or_create_passport(db_session, recipe1.id)

    req2 = _packaging_request(db_session, sku_id=sku.id)
    recipe2 = _verified_recipe(db_session, material, req2.id)
    passport2 = get_or_create_passport(db_session, recipe2.id)

    assert passport1.revision == 1
    assert passport2.revision == 2
    assert passport2.previous_passport_id == passport1.id
    assert passport2.passport_no != passport1.passport_no


def test_revision_chain_falls_back_to_packaging_request_without_sku(db_session):
    """SKU'suz bir talebin reçetesi V1 doğrulanır (pasaport 1) sonra fiziksel
    test başarısız olup V2 üretilip doğrulanırsa (aynı packaging_request_id),
    ikinci pasaport hâlâ revizyon zinciri kurmalı (SKU zorunlu değil)."""
    material = _material(db_session)
    req = _packaging_request(db_session)  # sku_id=None
    recipe_v1 = _verified_recipe(db_session, material, req.id, version=1)
    passport1 = get_or_create_passport(db_session, recipe_v1.id)

    recipe_v2 = _verified_recipe(db_session, material, req.id, version=2)
    passport2 = get_or_create_passport(db_session, recipe_v2.id)

    assert passport1.revision == 1
    assert passport2.revision == 2
    assert passport2.previous_passport_id == passport1.id
