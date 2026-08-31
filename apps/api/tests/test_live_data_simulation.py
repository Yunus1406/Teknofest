"""Aşama 10 canlı üretim simülasyonu — zaman damgalarının ilerlediğini,
dönemsel/kümülatif alanların doğru hesaplandığını ve verinin 'Makineden
Alınan' değil 'Simülasyon Verisi' olarak işaretlendiğini doğrular.

Faz B.6 — ayrıca tipli `WasteRecord` kırılımının `ProductionLiveData.
waste_kg` (dönemsel toplam, değişmeden kalması gereken alan) ile tutarlı
olduğunu ve `ProductionOrder`'ın opsiyonel üretim geçmişi alanlarının
simülasyon sonunda doldurulduğunu doğrular."""
import pytest

from app.models.enums import WasteType
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.production import ProductionOrder, WasteRecord
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.production_flow_service import simulate_live_data


@pytest.fixture()
def order(db_session):
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()
    material = Material(
        polymer_id=polymer.id, name="PE Virgin", material_type="virgin", density_g_cm3=0.92,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    db_session.add(material)
    line = ProductionLine(name="Hat-Test", layer_structure="A", layer_count=1, min_micron=10, max_micron=1000, supported_packaging_types=[])
    db_session.add(line)
    req = PackagingRequest(packaging_type="esnek film ambalaj", usage_area="t", product="t", target_market="t", food_contact=True, target_volume_units=1000, dimensions={})
    db_session.add(req)
    db_session.flush()
    recipe = Recipe(packaging_request_id=req.id, version=1, source="sistem_uretti", status="onerildi", total_micron=70.0)
    db_session.add(recipe)
    db_session.flush()
    db_session.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0))
    order = ProductionOrder(recipe_id=recipe.id, line_id=line.id, status="bekliyor", scheduled_qty_units=1000)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


def test_timestamps_advance_across_ticks(db_session, order):
    rows = simulate_live_data(db_session, order, ticks=5)
    timestamps = [r.ts for r in rows]
    assert len(set(timestamps)) == 5, "Tüm satırlar aynı zaman damgasını taşımamalı"
    assert timestamps == sorted(timestamps)


def test_cumulative_fields_are_running_sums_of_period_fields(db_session, order):
    rows = simulate_live_data(db_session, order, ticks=5)

    running_energy = 0.0
    running_waste = 0.0
    running_qty = 0
    for r in rows:
        running_energy += r.energy_kwh
        running_waste += r.waste_kg
        running_qty += r.period_produced_qty_units
        assert r.cumulative_energy_kwh == pytest.approx(running_energy, abs=0.01)
        assert r.cumulative_waste_kg == pytest.approx(running_waste, abs=0.01)
        assert r.produced_qty_units == running_qty

    # Kümülatif alanlar azalan olmamalı (monoton artan).
    energies = [r.cumulative_energy_kwh for r in rows]
    assert energies == sorted(energies)


def test_source_is_simulation_not_machine_data(db_session, order):
    rows = simulate_live_data(db_session, order, ticks=3)
    for r in rows:
        assert r.source == "simulasyon_verisi"
        assert r.source != "makineden_alinan"


def test_waste_records_reconcile_with_period_waste_kg(db_session, order):
    rows = simulate_live_data(db_session, order, ticks=5)
    waste_records = db_session.query(WasteRecord).filter_by(production_order_id=order.id).all()

    assert len(waste_records) > 0
    by_ts: dict = {}
    for wr in waste_records:
        by_ts.setdefault(wr.ts, []).append(wr)

    for row in rows:
        matching = by_ts.get(row.ts, [])
        assert matching, f"{row.ts} için WasteRecord bulunamadı"
        total = sum(wr.kg for wr in matching)
        assert total == pytest.approx(row.waste_kg, abs=0.001), (
            "WasteRecord toplamı ProductionLiveData.waste_kg ile tutarlı olmalı"
        )

    valid_types = {t.value for t in WasteType}
    for wr in waste_records:
        assert wr.waste_type in valid_types
        assert isinstance(wr.recoverable, bool)


def test_production_order_history_fields_populated_after_simulation(db_session, order):
    simulate_live_data(db_session, order, ticks=4)
    db_session.refresh(order)

    assert order.operator is not None
    assert order.actual_start is not None
    assert order.actual_end is not None
    assert order.actual_end > order.actual_start
    assert order.downtime_minutes is not None
    assert order.avg_micron is not None
    assert order.actual_layer_ratios
    assert "0" in order.actual_layer_ratios  # layer_index=0 (tek katmanlı test reçetesi)
