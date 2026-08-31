"""Aşama 1 (Ana Ekran) agregasyonu — hem 'yüzdeleri toplama' hatasının hem
de 'referanssız azaltım iddiası' hatasının düzeltildiğini doğrular."""
import pytest

from app.models.company import Company, Facility
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.optimization import OptimizationRun
from app.models.product_sku import ProductSku
from app.models.production import PhysicalTest, ProductionLiveData, ProductionOrder
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.dashboard_aggregation import (
    OPTIMIZASYONDA,
    TAMAMLANDI,
    TASLAK,
    TESTTE,
    URETIMDE,
    compute_case_status,
    compute_company_overview,
    compute_material_usage_totals,
    compute_realized_and_gains,
)


def _material(db, name, material_type, density=0.92, carbon=1.8, polymer_code="PE"):
    polymer = db.query(Polymer).filter_by(code=polymer_code).one_or_none()
    if polymer is None:
        polymer = Polymer(code=polymer_code, name=polymer_code, category="poliolefin", base_properties={})
        db.add(polymer)
        db.flush()
    m = Material(
        polymer_id=polymer.id, name=name, material_type=material_type, density_g_cm3=density,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=carbon,
    )
    db.add(m)
    db.flush()
    return m


def _request(db, packaging_type="esnek film ambalaj", length_mm=400, width_mm=300):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test", target_market="test",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": length_mm, "width_mm": width_mm},
    )
    db.add(req)
    db.flush()
    return req


def _recipe(db, request, material, total_micron=70.0, is_verified=False, version=1, line_id=None):
    recipe = Recipe(
        packaging_request_id=request.id, version=version, source="sistem_uretti",
        status="onerildi", total_micron=total_micron, is_verified=is_verified, line_id=line_id,
    )
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=total_micron))
    db.commit()
    db.refresh(recipe)
    return recipe


def _dummy_line(db, energy_kwh_per_kg=0.0, active=True):
    line = ProductionLine(
        name="Test Hattı", layer_structure="A", layer_count=1, min_micron=10, max_micron=1000,
        supported_packaging_types=[], energy_kwh_per_kg=energy_kwh_per_kg, active=active,
    )
    db.add(line)
    db.flush()
    return line


def _order_with_live_data(db, recipe, qty=1000, waste_kg=0.5, line=None):
    line_id = line.id if line is not None else _dummy_line(db).id
    order = ProductionOrder(recipe_id=recipe.id, line_id=line_id, status="tamamlandi", scheduled_qty_units=qty)
    db.add(order)
    db.flush()
    db.add(ProductionLiveData(production_order_id=order.id, produced_qty_units=qty, waste_kg=waste_kg, energy_kwh=1.0, line_speed_m_min=100.0, source="simulasyon_verisi"))
    db.commit()
    db.refresh(order)
    return order


# --- Vaka durumu -----------------------------------------------------------

def test_case_status_progression(db_session):
    material = _material(db_session, "PE Virgin", "virgin")
    req = _request(db_session)
    assert compute_case_status(db_session, req) == TASLAK

    db_session.add(OptimizationRun(packaging_request_id=req.id, parameters={}))
    db_session.commit()
    assert compute_case_status(db_session, req) == OPTIMIZASYONDA

    recipe = _recipe(db_session, req, material)
    order = _order_with_live_data(db_session, recipe)
    assert compute_case_status(db_session, req) == URETIMDE

    db_session.add(PhysicalTest(recipe_id=recipe.id, production_order_id=order.id, test_type="gramaj", value=1, unit="g", passed=True))
    db_session.commit()
    assert compute_case_status(db_session, req) == TESTTE

    recipe.is_verified = True
    db_session.commit()
    assert compute_case_status(db_session, req) == TAMAMLANDI


# --- Kütle bazlı toplam kullanım -------------------------------------------

def test_material_usage_totals_only_counts_recipes_with_production_orders(db_session):
    material = _material(db_session, "PE Virgin", "virgin")
    req = _request(db_session)

    # 4 finalist üretildi ama YALNIZCA biri üretime alındı (ProductionOrder aldı).
    chosen = _recipe(db_session, req, material, version=1)
    for v in range(2, 5):
        _recipe(db_session, req, material, version=v)  # ProductionOrder YOK -> sayılmamalı
    _order_with_live_data(db_session, chosen, qty=1000)

    totals = compute_material_usage_totals(db_session)

    assert totals.virgin_kg == pytest.approx(15.5, rel=0.02)
    assert totals.pcr_kg == 0.0
    # tek malzeme -> yüzde tam %100 olmalı, %2852 gibi imkansız değil.
    assert totals.pct(totals.virgin_kg) == pytest.approx(100.0)


def test_material_usage_percentages_always_sum_to_100(db_session):
    virgin = _material(db_session, "PE Virgin", "virgin")
    pcr = _material(db_session, "PE PCR", "pcr")
    req = _request(db_session)
    recipe = Recipe(packaging_request_id=req.id, version=1, source="sistem_uretti", status="onerildi", total_micron=70.0)
    db_session.add(recipe)
    db_session.flush()
    db_session.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=virgin.id, ratio_pct=70.0, thickness_micron=70.0))
    db_session.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=pcr.id, ratio_pct=30.0, thickness_micron=70.0))
    db_session.commit()
    db_session.refresh(recipe)
    _order_with_live_data(db_session, recipe, qty=1000)

    totals = compute_material_usage_totals(db_session)
    total_pct = totals.pct(totals.virgin_kg) + totals.pct(totals.pcr_kg) + totals.pct(totals.regranul_kg)
    assert total_pct == pytest.approx(100.0, abs=0.2)


# --- Referanssız azaltım iddiası olmamalı ----------------------------------

def test_no_reference_means_gains_are_none_but_realized_waste_is_shown(db_session):
    material = _material(db_session, "PE Virgin", "virgin")
    req = _request(db_session)
    recipe = _recipe(db_session, req, material, is_verified=True)
    _order_with_live_data(db_session, recipe, qty=1000, waste_kg=2.0)

    result = compute_realized_and_gains(db_session)

    assert result.realized_waste_kg == pytest.approx(2.0)
    assert result.carbon_reduction_kg_co2 is None
    assert result.prevented_waste_kg is None


def test_with_verified_reference_gains_are_computed(db_session):
    material_old = _material(db_session, "PE Virgin Eski", "virgin", carbon=1.8)
    material_new = _material(db_session, "PE PCR Yeni", "pcr", carbon=0.6)
    req1 = _request(db_session)
    reference = _recipe(db_session, req1, material_old, is_verified=True, version=1)
    _order_with_live_data(db_session, reference, qty=1000, waste_kg=3.0)

    req2 = _request(db_session)
    recipe = _recipe(db_session, req2, material_new, is_verified=True, version=1)
    _order_with_live_data(db_session, recipe, qty=1000, waste_kg=1.0)

    result = compute_realized_and_gains(db_session)

    assert result.carbon_reduction_kg_co2 is not None
    assert result.carbon_reduction_kg_co2 > 0  # yeni reçete daha düşük karbonlu malzeme kullanıyor
    assert result.prevented_waste_kg == pytest.approx(2.0, rel=0.05)  # 3.0 - 1.0 kg fire farkı


# --- Faz E.5: firma bazlı üst bilgi ----------------------------------------

def test_company_overview_none_when_no_company_registered(db_session):
    """Firma Profili formu hiç doldurulmadıysa (Company yok) uydurma bir
    isim gösterilmez, alanlar None kalır."""
    overview = compute_company_overview(db_session)
    assert overview.company_name is None
    assert overview.facility_name is None
    assert overview.active_line_count == 0
    assert overview.registered_material_count == 0
    assert overview.registered_sku_count == 0


def test_company_overview_reflects_registered_entities(db_session):
    company = Company(name="Test Ambalaj A.Ş.")
    db_session.add(company)
    db_session.flush()
    facility = Facility(company_id=company.id, name="Test Tesis-1")
    db_session.add(facility)

    _dummy_line(db_session, active=True)
    _dummy_line(db_session, active=True)
    _dummy_line(db_session, active=False)  # sayılmamalı

    _material(db_session, "PE Virgin Overview", "virgin")
    db_session.add(ProductSku(sku_code="OVW-1", product_name="X", packaging_type="x", usage_area="x", target_market="AB"))
    db_session.commit()

    overview = compute_company_overview(db_session)
    assert overview.company_name == "Test Ambalaj A.Ş."
    assert overview.facility_name == "Test Tesis-1"
    assert overview.active_line_count == 2
    assert overview.registered_material_count == 1
    assert overview.registered_sku_count == 1


# --- Faz E.5: önlenen virgin / enerji kazanımı -----------------------------

def test_prevented_virgin_and_energy_none_without_reference(db_session):
    line = _dummy_line(db_session, energy_kwh_per_kg=0.4)
    material = _material(db_session, "PE Virgin E5", "virgin")
    req = _request(db_session)
    recipe = _recipe(db_session, req, material, is_verified=True, line_id=line.id)
    _order_with_live_data(db_session, recipe, qty=1000, waste_kg=2.0, line=line)

    result = compute_realized_and_gains(db_session)

    assert result.prevented_virgin_kg is None
    assert result.energy_savings_kwh is None


def test_prevented_virgin_and_energy_computed_with_reference(db_session):
    old_line = _dummy_line(db_session, energy_kwh_per_kg=0.5)
    new_line = _dummy_line(db_session, energy_kwh_per_kg=0.3)

    material_old = _material(db_session, "PE Virgin Eski E5", "virgin", carbon=1.8)
    material_new = _material(db_session, "PE PCR Yeni E5", "pcr", carbon=0.6)

    req1 = _request(db_session)
    reference = _recipe(db_session, req1, material_old, is_verified=True, version=1, line_id=old_line.id)
    _order_with_live_data(db_session, reference, qty=1000, waste_kg=3.0, line=old_line)

    req2 = _request(db_session)
    recipe = _recipe(db_session, req2, material_new, is_verified=True, version=1, line_id=new_line.id)
    _order_with_live_data(db_session, recipe, qty=1000, waste_kg=1.0, line=new_line)

    result = compute_realized_and_gains(db_session)

    # Referans %100 virgin, yeni reçete %100 PCR -> önlenen virgin > 0.
    assert result.prevented_virgin_kg is not None
    assert result.prevented_virgin_kg > 0

    # Eski hat 0.5 kWh/kg, yeni hat 0.3 kWh/kg -> enerji kazanımı > 0.
    assert result.energy_savings_kwh is not None
    assert result.energy_savings_kwh > 0


def test_energy_savings_none_when_line_energy_data_missing(db_session):
    """İki hat da energy_kwh_per_kg=0.0 (varsayılan, "veri girilmedi" anlamına
    gelir) -- enerji kazanımı hesaplanmamalı, karbon/fire yine de hesaplanabilir."""
    old_line = _dummy_line(db_session, energy_kwh_per_kg=0.0)
    new_line = _dummy_line(db_session, energy_kwh_per_kg=0.0)

    material_old = _material(db_session, "PE Virgin Eski E5b", "virgin", carbon=1.8)
    material_new = _material(db_session, "PE PCR Yeni E5b", "pcr", carbon=0.6)

    req1 = _request(db_session)
    reference = _recipe(db_session, req1, material_old, is_verified=True, version=1, line_id=old_line.id)
    _order_with_live_data(db_session, reference, qty=1000, waste_kg=3.0, line=old_line)

    req2 = _request(db_session)
    recipe = _recipe(db_session, req2, material_new, is_verified=True, version=1, line_id=new_line.id)
    _order_with_live_data(db_session, recipe, qty=1000, waste_kg=1.0, line=new_line)

    result = compute_realized_and_gains(db_session)

    assert result.energy_savings_kwh is None
    assert result.carbon_reduction_kg_co2 is not None  # karbon hâlâ hesaplanabiliyor
    assert result.prevented_virgin_kg is not None
