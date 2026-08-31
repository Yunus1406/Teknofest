"""Faz D.1 — Optimizasyon aday sayılarının gerçekten firma verisinden
(Faz B hammadde/hat kütüphanesinden) dinamik olarak hesaplandığını
doğrular.

Bulunan gerçek bug: `candidate_generator.py`deki `MAX_STEPS_PER_MATERIAL`
sabiti eskiden 5'ti; `ratio_step_pct=10` ile bu, bir malzemenin gerçek
`max_recommended_ratio_pct`/hat uyumluluk oranı ne olursa olsun taramanın
HER ZAMAN %50'de kesilmesine yol açıyordu — %50'nin üzerindeki hiçbir PCR
limiti değişikliği aday sayısını etkilemiyordu. 20'ye çıkarıldı (bkz. aynı
dosyadaki yorum)."""
import pytest

from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest
from app.optimization.candidate_generator import describe_candidate_generation, generate_candidates
from app.services import optimization_service


@pytest.fixture()
def scenario(db_session):
    """A/B/A 3 katmanlı bir hat, tek bir PE virgin + tek bir PE PCR seçeneği.
    `db_session` fixture'ı doğrudan pytest'e enjekte edilir, bu fonksiyon
    sadece PCR malzemesinin `Material` nesnesini test gövdesine dışa açar
    ki testler onun `max_recommended_ratio_pct`'ini değiştirebilsin."""
    db = db_session
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()

    virgin = Material(
        polymer_id=polymer.id, name="PE Virgin Test", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    pcr = Material(
        polymer_id=polymer.id, name="PE PCR Test", material_type="pcr",
        food_contact_eligible=True, max_recommended_ratio_pct=40.0, cost_per_kg=20.0,
        carbon_factor_kg_co2_per_kg=0.6,
    )
    db.add_all([virgin, pcr])
    db.flush()

    line = ProductionLine(
        name="Test Hat", layer_structure="A/B/A", layer_count=3, min_micron=50, max_micron=90,
        supported_packaging_types=["esnek_film_ambalaj"],
    )
    db.add(line)
    db.flush()
    pcr_compat = LineMaterialCompatibility(line_id=line.id, material_id=pcr.id, max_ratio_pct=40.0)
    db.add(pcr_compat)
    db.add(LineMaterialCompatibility(line_id=line.id, material_id=virgin.id, max_ratio_pct=100.0))
    db.commit()

    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    db.refresh(line)
    db.refresh(pcr)
    db.refresh(pcr_compat)

    return {"db": db, "req": req, "line": line, "pcr": pcr, "pcr_compat": pcr_compat}


def _run(scenario) -> int:
    result = optimization_service.run_optimization(
        scenario["db"], scenario["req"].id, scenario["line"].id, ratio_step_pct=10
    )
    return result["generated_candidate_count"], result["generation_breakdown"]


# --- Bug regresyonu: %50 üzerindeki oran değişiklikleri artık etkili -------

def test_raising_pcr_ratio_cap_above_old_50pct_ceiling_changes_candidate_count(scenario):
    """Faz D.1'in ana regresyon testi: eski kodda 60->95 arası HİÇBİR fark
    yaratmazdı (her ikisi de içeride 50'ye kesiliyordu) -- artık yaratmalı."""
    scenario["pcr"].max_recommended_ratio_pct = 60.0
    scenario["pcr_compat"].max_ratio_pct = 60.0
    scenario["db"].commit()
    count_low, _ = _run(scenario)

    scenario["pcr"].max_recommended_ratio_pct = 95.0
    scenario["pcr_compat"].max_ratio_pct = 95.0
    scenario["db"].commit()
    count_high, _ = _run(scenario)

    assert count_low != count_high
    assert count_high > count_low


def test_lowering_pcr_ratio_cap_reduces_candidate_count(scenario):
    scenario["pcr"].max_recommended_ratio_pct = 40.0
    scenario["pcr_compat"].max_ratio_pct = 40.0
    scenario["db"].commit()
    count_before, _ = _run(scenario)

    scenario["pcr"].max_recommended_ratio_pct = 10.0
    scenario["pcr_compat"].max_ratio_pct = 10.0
    scenario["db"].commit()
    count_after, _ = _run(scenario)

    assert count_after < count_before


def test_removing_available_raw_material_reduces_candidate_count(scenario):
    count_with_pcr, _ = _run(scenario)

    scenario["db"].delete(scenario["pcr_compat"])
    scenario["db"].commit()
    count_without_pcr, _ = _run(scenario)

    assert count_without_pcr < count_with_pcr


# --- 'Adaylar Nasıl Oluşturuldu?' matematiği gerçek sayıyla birebir -------

def test_generation_breakdown_total_matches_actual_generated_count(scenario):
    generated_count, breakdown = _run(scenario)

    assert breakdown["total"] == generated_count

    product = 1
    for layer in breakdown["layers"]:
        product *= layer["variant_count"]
    assert product == generated_count
    assert str(generated_count) in breakdown["formula_text"]


def test_describe_candidate_generation_matches_generate_candidates_directly():
    """Servis katmanını hiç kullanmadan, candidate_generator seviyesinde de
    aynı tutarlılık -- iki fonksiyon aynı `_per_layer_variants` çağrısını
    paylaştığı için sapmaları matematiksel olarak imkansız."""
    from app.constraint_engine.types import LineSpec, MaterialSpec
    from app.optimization.candidate_generator import LayerMaterialOptions

    virgin = MaterialSpec(
        id="v1", name="Virgin", polymer_code="PE", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, degradation_factor=0.0,
        mfi_g_10min=None, cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    recycled = MaterialSpec(
        id="r1", name="PCR", polymer_code="PE", material_type="pcr",
        food_contact_eligible=True, max_recommended_ratio_pct=70.0, degradation_factor=0.1,
        mfi_g_10min=None, cost_per_kg=20.0, carbon_factor_kg_co2_per_kg=0.6,
    )
    line = LineSpec(
        id="l1", name="Test", layer_structure="A/B/A", layer_count=3, min_micron=50, max_micron=90,
        min_gsm=None, max_gsm=None, supported_packaging_types=[], material_max_ratio={"r1": 70.0},
    )
    layer_options = [
        LayerMaterialOptions(layer_label=lbl, virgin=virgin, recycled_options=[recycled])
        for lbl in ["A", "B", "A"]
    ]

    candidates = generate_candidates(line, layer_options, ratio_step_pct=10)
    breakdown = describe_candidate_generation(line, layer_options, ratio_step_pct=10)

    assert len(candidates) == breakdown["total"]
