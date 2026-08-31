"""Faz C.5 — Otomatik Optimizasyon Raporu veri toplama servisi. 16 bölümün
hepsinin gerçek veriden derlendiğini, referans yoksa yüzde azaltım
uydurulmadığını (Faz A kuralı), `RecipeSource.REFERANS` reçetelerde
optimizasyon-süreci/eleme bölümlerinin doğru atlandığını ve raporun hiçbir
yerinde "COP31 Uyumlu" gibi doğrulanmamış bir iddia üretilmediğini doğrular."""
import pytest

from app.models.enums import RecipeSource
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.optimization import OptimizationCandidate, OptimizationRun
from app.models.production import ProductionLiveData, ProductionOrder, SustainabilityResult
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer, RecipeMetric
from app.services.report_service import build_executive_summary, build_optimization_report_data
from app.services.production_flow_service import build_comparison


def _material(db, name="Test Malzeme"):
    polymer = db.query(Polymer).filter_by(code="PE").one_or_none()
    if polymer is None:
        polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
        db.add(polymer)
        db.flush()
    material = Material(
        polymer_id=polymer.id, name=name, material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(material)
    db.flush()
    return material


def _verified_recipe(db, material, packaging_type="esnek film ambalaj", source="sistem_uretti", version=1, thickness=70.0):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=version, source=source, status="dogrulandi",
        is_verified=True, total_micron=thickness,
    )
    db.add(recipe)
    db.flush()
    db.add(
        RecipeLayer(
            recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id,
            ratio_pct=100.0, thickness_micron=thickness,
        )
    )
    db.commit()
    db.refresh(recipe)
    return recipe


def _add_sustainability_result(db, recipe, **overrides):
    per_1000 = {
        "virgin_kg": 10.0, "pcr_kg": 2.0, "regranul_kg": 0.0, "karbon_kg_co2": 20.0,
        "karbon_veri_kalitesi": "tanimli_demo", "fire_kg": 1.0, "enerji_kwh": 5.0,
    }
    per_1000.update(overrides)
    db.add(SustainabilityResult(recipe_id=recipe.id, per_1000_units=per_1000, is_actual=True))
    db.commit()


def _add_metrics(db, recipe, virgin_pct=100.0, pcr_pct=0.0, regranul_pct=0.0, carbon=1.8, cost=30.0):
    for metric_type, value, unit in [
        ("virgin_kullanimi", virgin_pct, "%"), ("pcr_kullanimi", pcr_pct, "%"),
        ("regranul_kullanimi", regranul_pct, "%"), ("karbon", carbon, "kg_co2/kg"), ("maliyet", cost, "TL/kg"),
    ]:
        db.add(
            RecipeMetric(
                recipe_id=recipe.id, metric_type=metric_type, value=value, unit=unit,
                is_estimated=True, data_source_type="hesaplanan",
            )
        )
    db.commit()


# --- Faz A kuralı: referans yoksa % azaltım uydurulmaz ---------------------

def test_no_reference_means_absolute_performance_not_percentage(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["referans_recete"]["has_reference"] is False
    assert data["referans_recete"]["note"] == "Doğrulanmış referans bulunmamaktadır."
    assert data["yonetici_ozeti"]["has_reference"] is False
    assert data["yonetici_ozeti"]["gains_pct"] is None
    assert data["yonetici_ozeti"]["realized_absolute_per_1000_units"] is not None
    assert "%" not in data["yonetici_ozeti"]["narrative"] or "hesaplanmadı" in data["yonetici_ozeti"]["narrative"]


def test_reference_present_computes_real_gains_not_hardcoded(db_session):
    material = _material(db_session)
    old_recipe = _verified_recipe(db_session, material, version=1, thickness=100.0)
    _add_metrics(db_session, old_recipe, virgin_pct=100.0, pcr_pct=0.0, carbon=2.0, cost=40.0)
    _add_sustainability_result(db_session, old_recipe, fire_kg=2.0, enerji_kwh=10.0)

    new_recipe = _verified_recipe(db_session, material, version=1, thickness=70.0)
    _add_metrics(db_session, new_recipe, virgin_pct=80.0, pcr_pct=20.0, carbon=1.5, cost=32.0)
    _add_sustainability_result(db_session, new_recipe, fire_kg=1.0, enerji_kwh=6.0)

    data = build_optimization_report_data(db_session, new_recipe.id)

    assert data["referans_recete"]["has_reference"] is True
    gains = data["yonetici_ozeti"]["gains_pct"]
    assert gains is not None
    # 100 -> 80 virgin: %20 azalım
    assert gains["virgin_azalimi_pct"] == pytest.approx(20.0)
    # 0 -> 20 pcr: eski değer 0 olduğundan (bölme koruması) None kalmalı
    assert gains["pcr_artisi_pct"] is None
    # 2.0 -> 1.5 karbon: %25 azalım
    assert gains["karbon_azaltimi_pct"] == pytest.approx(25.0)
    # 40 -> 32 maliyet: %20 azalım
    assert gains["maliyet_azaltimi_pct"] == pytest.approx(20.0)
    # 2.0 -> 1.0 fire: %50 azalım
    assert gains["fire_azaltimi_pct"] == pytest.approx(50.0)
    # 10.0 -> 6.0 enerji: %40 azalım
    assert gains["enerji_azaltimi_pct"] == pytest.approx(40.0)
    assert "%30" not in data["yonetici_ozeti"]["narrative"]  # asla sabit/uydurma bir varsayılan değil


# --- RecipeSource.REFERANS reçetelerde §5/§6 doğru atlanır ------------------

def test_reference_sourced_recipe_skips_optimization_process_section(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material, source=RecipeSource.REFERANS.value)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["optimizasyon_sureci"]["applicable"] is False
    assert "referanstan geldi" in data["optimizasyon_sureci"]["note"]
    assert data["neden_elendi"]["applicable"] is False
    assert data["neden_elendi"]["items"] == []


# --- Neden Elendi (C.4 entegrasyonu) ---------------------------------------

def test_notable_eliminated_appears_when_run_has_data(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material, source=RecipeSource.URETILDI.value)
    _add_sustainability_result(db_session, recipe)

    run = OptimizationRun(
        packaging_request_id=recipe.packaging_request_id,
        parameters={"ratio_step_pct": 10, "candidate_count_generated": 50, "survived_constraint_engine_count": 10},
        notable_eliminated=[{"composition_summary": "test", "reasons": ["test neden"], "summary_text": "test özet"}],
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(
        OptimizationCandidate(
            run_id=run.id, recipe_id=recipe.id, score=0.9, rank=1, is_finalist=True,
            score_breakdown={}, decision_basis={},
        )
    )
    db_session.commit()

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["optimizasyon_sureci"]["applicable"] is True
    assert data["optimizasyon_sureci"]["generated_candidate_count"] == 50
    assert data["optimizasyon_sureci"]["survived_constraint_engine_count"] == 10
    assert data["optimizasyon_sureci"]["finalist_count"] == 1
    assert data["neden_elendi"]["applicable"] is True
    assert data["neden_elendi"]["note"] is None
    assert len(data["neden_elendi"]["items"]) == 1
    assert data["neden_elendi"]["items"][0]["summary_text"] == "test özet"


def test_notable_eliminated_honest_fallback_when_run_predates_c4(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material, source=RecipeSource.URETILDI.value)
    _add_sustainability_result(db_session, recipe)

    run = OptimizationRun(packaging_request_id=recipe.packaging_request_id, parameters={})
    db_session.add(run)
    db_session.flush()
    db_session.add(
        OptimizationCandidate(
            run_id=run.id, recipe_id=recipe.id, score=0.9, rank=1, is_finalist=True,
            score_breakdown={}, decision_basis={},
        )
    )
    db_session.commit()

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["neden_elendi"]["applicable"] is True
    assert "kaydedilmedi" in data["neden_elendi"]["note"]
    assert data["neden_elendi"]["items"] == []


# --- PPWR ön uyum ifadesi ----------------------------------------------------

def test_ppwr_section_carries_legal_disclaimer(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    assert "hukuki uygunluk sertifikasyonu değildir" in data["ppwr_on_uyum"]["disclaimer"]


# --- İklim/Döngüsellik: doğrulanmamış uygunluk iddiası ASLA yok -------------

def test_climate_section_never_claims_cop31_compliance(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    import json
    full_text = json.dumps(data, ensure_ascii=False, default=str)
    assert "COP31 Uyumlu" not in full_text
    assert "Uyumlu" not in data["iklim_dongusellik"]["perspective_label"]
    assert data["iklim_dongusellik"]["perspective_label"] == "İklim ve Döngüsellik Perspektifi"


# --- Ön koşul: sadece doğrulanmış reçeteler ----------------------------------

def test_unverified_recipe_is_rejected(db_session):
    material = _material(db_session)
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db_session.add(req)
    db_session.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, source="sistem_uretti",
        status="onerildi", is_verified=False,
    )
    db_session.add(recipe)
    db_session.commit()
    db_session.refresh(recipe)

    with pytest.raises(ValueError, match="doğrulanmış"):
        build_optimization_report_data(db_session, recipe.id)


# --- Gerçek üretim sonuçları (§9) --------------------------------------------

def test_production_results_section_aggregates_real_live_data(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_sustainability_result(db_session, recipe)

    line = ProductionLine(
        name="Test Hat", layer_structure="A", layer_count=1, min_micron=10, max_micron=1000,
        supported_packaging_types=[],
    )
    db_session.add(line)
    db_session.flush()

    order = ProductionOrder(recipe_id=recipe.id, line_id=line.id, status="tamamlandi", scheduled_qty_units=1000)
    db_session.add(order)
    db_session.flush()
    db_session.add(
        ProductionLiveData(
            production_order_id=order.id, produced_qty_units=500, period_produced_qty_units=500,
            material_consumption={material.id: 5.0}, line_speed_m_min=100.0,
            energy_kwh=2.0, cumulative_energy_kwh=2.0, waste_kg=0.5, cumulative_waste_kg=0.5,
            source="simulasyon_verisi",
        )
    )
    db_session.add(
        ProductionLiveData(
            production_order_id=order.id, produced_qty_units=1000, period_produced_qty_units=500,
            material_consumption={material.id: 5.0}, line_speed_m_min=110.0,
            energy_kwh=2.0, cumulative_energy_kwh=4.0, waste_kg=0.3, cumulative_waste_kg=0.8,
            source="simulasyon_verisi",
        )
    )
    db_session.commit()

    data = build_optimization_report_data(db_session, recipe.id)

    orders = data["gercek_uretim_sonuclari"]["orders"]
    assert len(orders) == 1
    assert orders[0]["total_produced_units"] == 1000
    assert orders[0]["total_energy_kwh"] == pytest.approx(4.0)
    assert orders[0]["total_waste_kg"] == pytest.approx(0.8)
    assert orders[0]["material_consumption_kg"][material.id] == pytest.approx(10.0)
    assert orders[0]["data_source"] == "simulasyon_verisi"
