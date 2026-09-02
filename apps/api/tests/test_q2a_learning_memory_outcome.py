"""Faz Q.0/Q.2 (Madde 24) düzeltmesi — `causal_chain_for_recipe()`'nin her
düğümüne AÇIK bir "outcome" (basarili/basarisiz/beklemede) ve
başarısızlık nedeni eklendiğini doğrular. Önceden sadece ham
`physical_test_summary` sayıları vardı, bir düğümün GERÇEKTEN başarısız
olduğunu anlamak için dolaylı çıkarım gerekiyordu."""
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.production import ProductionOrder
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.learning_memory_service import causal_chain_for_recipe
from app.services.production_flow_service import submit_physical_tests


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


def _recipe_with_layer(db, material, thickness=70.0):
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="t", product="t", target_market="t",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(packaging_request_id=req.id, version=1, source="sistem_uretti", status="onerildi", total_micron=thickness)
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=thickness))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_root_node_with_no_tests_is_beklemede(db_session):
    material = _material(db_session)
    recipe = _recipe_with_layer(db_session, material)

    chain = causal_chain_for_recipe(db_session, recipe)

    assert chain[0]["outcome"] == "beklemede"
    assert chain[0]["basarisizlik_nedeni"] is None


def test_verified_node_is_basarili(db_session):
    material = _material(db_session)
    recipe = _recipe_with_layer(db_session, material)
    recipe.is_verified = True
    db_session.commit()

    chain = causal_chain_for_recipe(db_session, recipe)

    assert chain[0]["outcome"] == "basarili"
    assert chain[0]["basarisizlik_nedeni"] is None


def test_failed_physical_test_marks_node_basarisiz_with_real_reason(db_session):
    material = _material(db_session)
    line = ProductionLine(name="Test Hat", layer_structure="A", layer_count=1, min_micron=10, max_micron=1000, supported_packaging_types=[])
    db_session.add(line)
    db_session.flush()
    recipe = _recipe_with_layer(db_session, material)
    recipe.line_id = line.id
    order = ProductionOrder(recipe_id=recipe.id, line_id=line.id, status="tamamlandi", scheduled_qty_units=1000)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    submit_physical_tests(
        db_session, order,
        [{"test_type": "kalinlik", "value": 40.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None}],
    )
    db_session.refresh(recipe)
    new_version = db_session.query(Recipe).filter_by(parent_recipe_id=recipe.id).one()

    chain = causal_chain_for_recipe(db_session, new_version)

    # chain[0] = orijinal (başarısız test yapılan) reçete
    assert chain[0]["outcome"] == "basarisiz"
    assert chain[0]["basarisizlik_nedeni"] is not None
    assert "kalinlik" in chain[0]["basarisizlik_nedeni"]
    assert "40.0" in chain[0]["basarisizlik_nedeni"]
    assert "63.0" in chain[0]["basarisizlik_nedeni"]

    # chain[1] = yeni açılan taslak, henüz kendi testi yok -> beklemede
    assert chain[1]["outcome"] == "beklemede"
    assert chain[1]["basarisizlik_nedeni"] is None
