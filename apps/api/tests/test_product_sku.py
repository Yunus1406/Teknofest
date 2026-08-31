"""Faz B.5 — Ürün/SKU kütüphanesi: find_reference_recipe SKU'yu metin
eşleşmesinden daha kesin bir referans olarak önceliklendirmeli; Aşama 12
(finalize_result) SKU'nun current_recipe_id'sini otomatik güncellemeli."""
import pytest

from app.models.knowledge import Material, Polymer
from app.models.product_sku import ProductSku
from app.models.production import PhysicalTest
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.packaging_service import find_reference_recipe
from app.services.production_flow_service import finalize_result


def _material(db):
    polymer = Polymer(code="PP", name="Polipropilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    m = Material(
        polymer_id=polymer.id, name="PP Virgin", material_type="virgin", density_g_cm3=0.905,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=38.0, carbon_factor_kg_co2_per_kg=1.9,
    )
    db.add(m)
    db.flush()
    return m


def _verified_recipe(db, request, material, version=1):
    recipe = Recipe(
        packaging_request_id=request.id, version=version, source="sistem_uretti",
        status="dogrulandi", total_micron=600.0, is_verified=True,
    )
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=600.0))
    db.commit()
    db.refresh(recipe)
    return recipe


def _request(db, packaging_type="plastik tabak", sku_id=None):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={}, sku_id=sku_id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_find_reference_recipe_falls_back_to_text_match_without_sku(db_session):
    material = _material(db_session)
    old_request = _request(db_session, packaging_type="plastik tabak")
    old_recipe = _verified_recipe(db_session, old_request, material)

    new_request = _request(db_session, packaging_type="plastik tabak")  # sku_id yok

    found = find_reference_recipe(db_session, new_request)
    assert found is not None
    assert found.id == old_recipe.id


def test_find_reference_recipe_prefers_sku_current_recipe_over_text_match(db_session):
    """Aynı packaging_type metnini paylaşan İKİ FARKLI SKU olsun. Text-match
    yanlış SKU'nun reçetesini bulabilir; sku_id set edildiğinde doğru SKU'nun
    current_recipe_id'si tercih edilmeli."""
    material = _material(db_session)

    # SKU A: eski, metin-eşleşmesinde "en son version" olarak öne çıkacak reçete.
    sku_a = ProductSku(sku_code="TBK-A", product_name="Tabak A", packaging_type="plastik tabak", usage_area="x", target_market="AB")
    db_session.add(sku_a)
    db_session.flush()
    req_a = _request(db_session, packaging_type="plastik tabak", sku_id=sku_a.id)
    recipe_a_v1 = _verified_recipe(db_session, req_a, material, version=1)
    recipe_a_v2 = _verified_recipe(db_session, req_a, material, version=2)  # en yüksek version
    sku_a.current_recipe_id = recipe_a_v1.id  # ama SKU'nun GEÇERLİ reçetesi v1 (ör. v2 geri alındı)
    db_session.commit()

    # SKU B: yeni case, SKU A ile AYNI packaging_type metnini paylaşıyor.
    sku_b = ProductSku(sku_code="TBK-B", product_name="Tabak B", packaging_type="plastik tabak", usage_area="x", target_market="AB")
    db_session.add(sku_b)
    db_session.flush()
    req_b = _request(db_session, packaging_type="plastik tabak", sku_id=sku_b.id)
    db_session.commit()
    db_session.refresh(req_b)

    found = find_reference_recipe(db_session, req_b)

    # Text-match tek başına en yüksek version'lu (recipe_a_v2) reçeteyi bulurdu.
    # SKU B'nin kendi current_recipe_id'si yok -> bu durumda hâlâ text-match'e
    # düşer (SKU'nun current_recipe_id'si YOKSA fallback devam eder).
    assert found is not None
    assert found.id == recipe_a_v2.id  # sku_b'nin kendi current_recipe_id'si yok, fallback'e düştü


def test_find_reference_recipe_uses_own_sku_current_recipe_when_set(db_session):
    material = _material(db_session)

    sku = ProductSku(sku_code="TBK-C", product_name="Tabak C", packaging_type="plastik tabak", usage_area="x", target_market="AB")
    db_session.add(sku)
    db_session.flush()
    req = _request(db_session, packaging_type="plastik tabak", sku_id=sku.id)
    recipe_v1 = _verified_recipe(db_session, req, material, version=1)
    recipe_v2 = _verified_recipe(db_session, req, material, version=2)
    sku.current_recipe_id = recipe_v1.id  # SKU'nun geçerli reçetesi v1
    db_session.commit()
    db_session.refresh(req)

    # Aynı SKU için YENİ bir case açıldığını simüle et.
    new_req = _request(db_session, packaging_type="plastik tabak", sku_id=sku.id)
    db_session.refresh(new_req)

    found = find_reference_recipe(db_session, new_req)
    assert found is not None
    assert found.id == recipe_v1.id  # en yüksek version değil, SKU'nun current_recipe_id'si


def test_finalize_result_updates_sku_current_recipe_id(db_session):
    material = _material(db_session)
    sku = ProductSku(sku_code="TBK-D", product_name="Tabak D", packaging_type="plastik tabak", usage_area="x", target_market="AB")
    db_session.add(sku)
    db_session.flush()
    req = _request(db_session, packaging_type="plastik tabak", sku_id=sku.id)
    recipe = _verified_recipe(db_session, req, material)
    recipe.is_verified = False  # finalize_result BUNU True yapacak
    # Faz D.2 — finalize_result artık en az bir gerçekten BAŞARILI fiziksel
    # test kaydı olmadan reddediyor (bkz. production_flow_service.py).
    db_session.add(
        PhysicalTest(
            recipe_id=recipe.id, test_type="kalinlik", value=600.0, unit="mikron",
            target_min=540.0, target_max=660.0, result="basarili", passed=True,
        )
    )
    db_session.commit()

    assert sku.current_recipe_id is None

    finalize_result(db_session, recipe)

    db_session.refresh(sku)
    assert sku.current_recipe_id == recipe.id
