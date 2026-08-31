"""Faz G.4 — Aşama 5'in 5 kademeli firma hafızası taraması. Kademe 1
(aynı SKU) ve kademe 2 (aynı ambalaj türü) zaten Faz B.5'te vardı ve
`tests/test_product_sku.py`'de test ediliyor (bu testler DEĞİŞMEDEN geçiyor,
bkz. `find_reference_recipe` geriye dönük uyumluluğu); burada SADECE YENİ
kademeler (3-5) ve `evidence_count`/`generate_initial_recipe`'in yeni
`reference_search_evidence` alanı test edilir."""
import pytest

from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.packaging_service import find_reference_recipe_with_evidence, generate_initial_recipe


def _material(db):
    polymer = Polymer(code="PP", name="Polipropilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    m = Material(
        polymer_id=polymer.id, name="PP Virgin G4 Test", material_type="virgin", density_g_cm3=0.905,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=38.0, carbon_factor_kg_co2_per_kg=1.9,
    )
    db.add(m)
    db.flush()
    return m


def _request(db, packaging_type="plastik tabak", usage_area="test", target_thickness_micron=None, target_gsm=None, sku_id=None):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area=usage_area, product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={}, sku_id=sku_id,
        target_thickness_micron=target_thickness_micron, target_gsm=target_gsm,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def _verified_recipe(db, request, material, version=1, line_id=None):
    recipe = Recipe(
        packaging_request_id=request.id, version=version, source="sistem_uretti", line_id=line_id,
        status="dogrulandi", total_micron=600.0, is_verified=True,
    )
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=600.0))
    db.commit()
    db.refresh(recipe)
    return recipe


def _line(db, **kwargs):
    defaults = dict(name="Test Hat G4", layer_structure="A", layer_count=1, min_micron=10, max_micron=1000, supported_packaging_types=[])
    defaults.update(kwargs)
    line = ProductionLine(**defaults)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


# --- Kademe 3: benzer kullanım alanı ---------------------------------------

def test_tier3_similar_usage_area_matches_across_different_packaging_types(db_session):
    material = _material(db_session)
    old_req = _request(db_session, packaging_type="esnek film ambalaj", usage_area="dondurulmuş gıda")
    old_recipe = _verified_recipe(db_session, old_req, material)

    # Farklı ambalaj türü ama AYNI kullanım alanı -> kademe 2 boş, kademe 3 eşleşmeli.
    new_req = _request(db_session, packaging_type="plastik kap", usage_area="dondurulmuş gıda")

    result = find_reference_recipe_with_evidence(db_session, new_req)

    assert result.recipe is not None
    assert result.recipe.id == old_recipe.id
    assert result.tier == "benzer_kullanim_alani"
    assert result.evidence_count == 1


def test_tier3_not_used_when_tier2_already_matched(db_session):
    """Aynı ambalaj türünde bir eşleşme varsa (kademe 2), kademe 3 hiç
    denenmemeli -- kademe 2'nin sonucu döner."""
    material = _material(db_session)
    same_type_req = _request(db_session, packaging_type="plastik tabak", usage_area="A")
    same_type_recipe = _verified_recipe(db_session, same_type_req, material)

    same_usage_req = _request(db_session, packaging_type="farklı ambalaj türü", usage_area="B")
    _verified_recipe(db_session, same_usage_req, material)

    new_req = _request(db_session, packaging_type="plastik tabak", usage_area="B")

    result = find_reference_recipe_with_evidence(db_session, new_req)
    assert result.tier == "ayni_ambalaj_turu"
    assert result.recipe.id == same_type_recipe.id


# --- Kademe 4: benzer teknik şartlar -----------------------------------------

def test_tier4_similar_technical_specs_within_tolerance(db_session):
    material = _material(db_session)
    old_req = _request(
        db_session, packaging_type="tip A", usage_area="alan A", target_thickness_micron=600.0, target_gsm=45.0,
    )
    old_recipe = _verified_recipe(db_session, old_req, material)

    # %10 sapma (±%20 tolerans içinde) -> eşleşmeli.
    new_req = _request(
        db_session, packaging_type="tip B", usage_area="alan B", target_thickness_micron=660.0, target_gsm=49.0,
    )

    result = find_reference_recipe_with_evidence(db_session, new_req)

    assert result.recipe is not None
    assert result.recipe.id == old_recipe.id
    assert result.tier == "benzer_teknik_sartlar"


def test_tier4_outside_tolerance_does_not_match(db_session):
    material = _material(db_session)
    old_req = _request(
        db_session, packaging_type="tip A", usage_area="alan A", target_thickness_micron=600.0,
    )
    _verified_recipe(db_session, old_req, material)

    # %50 sapma -> ±%20 toleransın dışında, eşleşmemeli.
    new_req = _request(
        db_session, packaging_type="tip B", usage_area="alan B", target_thickness_micron=900.0,
    )

    result = find_reference_recipe_with_evidence(db_session, new_req)
    assert result.recipe is None


def test_tier4_skipped_when_no_target_specs_entered(db_session):
    """G.1'in yeni alanları hiç girilmemişse (None), 'benzerlik' iddiası
    ANLAMSIZ olur -- kademe 4 hiç denenmemeli."""
    material = _material(db_session)
    old_req = _request(db_session, packaging_type="tip A", usage_area="alan A", target_thickness_micron=600.0)
    _verified_recipe(db_session, old_req, material)

    new_req = _request(db_session, packaging_type="tip B", usage_area="alan B")  # target_thickness_micron=None

    result = find_reference_recipe_with_evidence(db_session, new_req)
    assert result.recipe is None


# --- Kademe 5: aynı hat -----------------------------------------------------

def test_tier5_same_line_matches_when_nothing_else_does(db_session):
    material = _material(db_session)
    line = _line(db_session, name="Ortak Hat")

    old_req = _request(db_session, packaging_type="tip A", usage_area="alan A")
    old_recipe = _verified_recipe(db_session, old_req, material, line_id=line.id)

    new_req = _request(db_session, packaging_type="tip B", usage_area="alan B")

    result = find_reference_recipe_with_evidence(db_session, new_req, line_id=line.id)

    assert result.recipe is not None
    assert result.recipe.id == old_recipe.id
    assert result.tier == "ayni_hat"


def test_tier5_not_used_without_line_id(db_session):
    material = _material(db_session)
    line = _line(db_session, name="Ortak Hat 2")
    old_req = _request(db_session, packaging_type="tip A", usage_area="alan A")
    _verified_recipe(db_session, old_req, material, line_id=line.id)

    new_req = _request(db_session, packaging_type="tip B", usage_area="alan B")

    result = find_reference_recipe_with_evidence(db_session, new_req)  # line_id verilmedi
    assert result.recipe is None


# --- Hiçbir kademe eşleşmezse -----------------------------------------------

def test_no_tier_matches_returns_none_evidence(db_session):
    new_req = _request(db_session, packaging_type="tamamen yeni tür", usage_area="tamamen yeni alan")
    result = find_reference_recipe_with_evidence(db_session, new_req)
    assert result.recipe is None
    assert result.tier is None
    assert result.evidence_count == 0
    assert result.candidate_recipe_ids == []


# --- generate_initial_recipe: reference_search_evidence gerçekten yazılıyor -

def test_generate_initial_recipe_stores_evidence_when_reference_found(db_session):
    material = _material(db_session)
    line = _line(db_session, name="Üretim Hattı G4", supported_packaging_types=["plastik tabak"])
    old_req = _request(db_session, packaging_type="plastik tabak", usage_area="alan A")
    _verified_recipe(db_session, old_req, material)

    new_req = _request(db_session, packaging_type="plastik tabak", usage_area="alan A")
    line.material_compatibility  # ilişki erişimi (lazy-load tetikleme, hata değil)

    recipe = generate_initial_recipe(db_session, new_req, line)

    assert recipe.reference_search_evidence is not None
    assert recipe.reference_search_evidence["tier"] == "ayni_ambalaj_turu"
    assert recipe.reference_search_evidence["evidence_count"] == 1


def test_generate_initial_recipe_evidence_none_when_no_reference(db_session):
    line = _line(db_session, name="Boş Hat G4", supported_packaging_types=["hiç kimsenin kullanmadığı tür"])
    # generate_initial_recipe, hiç referans bulunamadığında bilgi tabanından
    # virgin bir malzeme arar -- ValueError'a düşmemesi için burada kuruyoruz.
    polymer = Polymer(code="PPX", name="Polipropilen X", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()
    db_session.add(
        Material(
            polymer_id=polymer.id, name="PPX Virgin", material_type="virgin", density_g_cm3=0.9,
            degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        )
    )
    db_session.commit()

    new_req = _request(db_session, packaging_type="hiç kimsenin kullanmadığı tür", usage_area="tamamen yeni")

    recipe = generate_initial_recipe(db_session, new_req, line)

    assert recipe.reference_search_evidence is None
    assert recipe.source == "sistem_uretti"
