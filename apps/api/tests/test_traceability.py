"""Faz B.9 — Firma Hafızası Zinciri. Yeni tablo yok; bilinen bir demo
reçetesi için Company->Facility->Machine->SKU->Recipe->Material->
ProductionOrder->WasteRecord->PhysicalTest->Regulation->CarbonEF zincirinin
UÇTAN UCA DOLU döndüğünü doğrular."""
import pytest

from app.models.company import Company, Facility
from app.models.infrastructure import ProductionLine
from app.models.knowledge import CarbonEmissionFactor, Material, Polymer, Regulation
from app.models.product_sku import ProductSku
from app.models.production import PhysicalTest, ProductionOrder, WasteRecord
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer, RegulatoryAssessment
from app.services.traceability_service import build_recipe_traceability


@pytest.fixture()
def full_chain(db_session):
    company = Company(name="Zincir Test A.Ş.")
    db_session.add(company)
    db_session.flush()
    facility = Facility(company_id=company.id, name="Zincir Test Tesis")
    db_session.add(facility)
    db_session.flush()
    line = ProductionLine(
        facility_id=facility.id, name="Zincir Test Hattı", layer_structure="A",
        layer_count=1, min_micron=10, max_micron=1000, supported_packaging_types=[],
    )
    db_session.add(line)
    db_session.flush()

    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()
    ef = CarbonEmissionFactor(
        material_key="Zincir Test EF", ef_value=1.2, source="DEMO/VARSAYIMSAL — kaynak yok",
        is_demo_placeholder=True,
    )
    db_session.add(ef)
    db_session.flush()
    material = Material(
        polymer_id=polymer.id, name="Zincir Test Malzeme", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.2, carbon_ef_id=ef.id,
    )
    db_session.add(material)
    db_session.flush()

    sku = ProductSku(
        sku_code="ZNC-001", product_name="Zincir Test Ürünü", packaging_type="esnek film ambalaj",
        usage_area="test", target_market="AB", food_contact=True, dimensions={},
    )
    db_session.add(sku)
    db_session.flush()

    reg = Regulation(
        code="ZNC-TEST-REG", title="Zincir Test Maddesi", category="test",
        description="test", criteria={}, applicable_packaging_types=[],
    )
    db_session.add(reg)
    db_session.flush()

    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={}, sku_id=sku.id,
    )
    db_session.add(req)
    db_session.flush()
    db_session.add(
        RegulatoryAssessment(
            packaging_request_id=req.id, regulation_id=reg.id,
            verdict="inceleme_gerekli", reasoning="Zincir test gerekçesi",
        )
    )

    recipe = Recipe(
        packaging_request_id=req.id, version=1, source="sistem_uretti", status="dogrulandi",
        is_verified=True, line_id=line.id, total_micron=70.0, total_gsm=None,
    )
    db_session.add(recipe)
    db_session.flush()
    db_session.add(
        RecipeLayer(
            recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id,
            ratio_pct=100.0, thickness_micron=70.0,
        )
    )

    order = ProductionOrder(recipe_id=recipe.id, line_id=line.id, status="tamamlandi", scheduled_qty_units=1000)
    db_session.add(order)
    db_session.flush()
    db_session.add(WasteRecord(production_order_id=order.id, waste_type="kenar_firesi", kg=1.5, recoverable=True))
    db_session.add(
        PhysicalTest(
            recipe_id=recipe.id, production_order_id=order.id, test_type="kalinlik",
            value=70.0, unit="mikron", passed=True,
        )
    )
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


def test_traceability_chain_is_fully_populated_for_known_recipe(db_session, full_chain):
    result = build_recipe_traceability(db_session, full_chain.id)

    assert result is not None
    assert result["recipe_id"] == full_chain.id
    assert result["company"]["name"] == "Zincir Test A.Ş."
    assert result["facility"]["name"] == "Zincir Test Tesis"
    assert result["machine"]["name"] == "Zincir Test Hattı"
    assert result["sku"]["sku_code"] == "ZNC-001"
    assert result["packaging_request"]["packaging_type"] == "esnek film ambalaj"
    assert result["recipe"]["is_verified"] is True

    assert len(result["layers"]) == 1
    assert result["layers"][0]["material"]["name"] == "Zincir Test Malzeme"
    assert result["layers"][0]["carbon_ef"]["is_demo_placeholder"] is True

    assert len(result["production_orders"]) == 1
    assert len(result["production_orders"][0]["waste_records"]) == 1
    assert result["production_orders"][0]["waste_records"][0]["waste_type"] == "kenar_firesi"

    assert len(result["physical_tests"]) == 1
    assert result["physical_tests"][0]["test_type"] == "kalinlik"

    assert len(result["regulatory_assessments"]) == 1
    assert result["regulatory_assessments"][0]["regulation_code"] == "ZNC-TEST-REG"


def test_traceability_returns_none_for_unknown_recipe(db_session):
    assert build_recipe_traceability(db_session, "no-such-recipe-id") is None


def test_traceability_handles_recipe_without_line_or_sku(db_session):
    """Reçete henüz bir hatta atanmamışsa (ör. Aşama 5 öncesi) veya talebin
    bir SKU'su yoksa zincir ÇÖKMEMELİ — o dallar sadece None döner."""
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db_session.add(req)
    db_session.flush()
    recipe = Recipe(packaging_request_id=req.id, version=1, source="sistem_uretti", status="taslak")
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)

    result = build_recipe_traceability(db_session, recipe.id)

    assert result is not None
    assert result["machine"] is None
    assert result["facility"] is None
    assert result["company"] is None
    assert result["sku"] is None
    assert result["layers"] == []
    assert result["production_orders"] == []
