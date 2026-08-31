"""Faz B.2 — PCR/PIR single-table inheritance ayrımı + Karbon EF kütüphanesi."""
import pytest

from app.models.knowledge import CarbonEmissionFactor, Material, PcrMaterial, PirMaterial, Polymer
from app.services.carbon import TANIMLANMADI, TANIMLI_DEMO, TANIMLI_GERCEK, resolve_carbon_ef, worst_status


def _polymer(db):
    p = Polymer(code="PP", name="Polipropilen", category="poliolefin", base_properties={})
    db.add(p)
    db.flush()
    return p


# --- STI: PCR ve PIR ayrı sınıflar, kendi alan setleri ----------------------

def test_pcr_and_pir_are_distinct_python_classes_sharing_one_table(db_session):
    polymer = _polymer(db_session)
    pcr = PcrMaterial(
        polymer_id=polymer.id, name="Test PCR", material_type="pcr",
        contamination_level="düşük", odor_level="yok", technical_constraints="test",
        food_contact_eligible=True, max_recommended_ratio_pct=50, cost_per_kg=30,
        carbon_factor_kg_co2_per_kg=0.6,
    )
    pir = PirMaterial(
        polymer_id=polymer.id, name="Test PIR", material_type="regranul",
        source_process="Film Fire Geri Kazanımı",
        food_contact_eligible=False, max_recommended_ratio_pct=30, cost_per_kg=24,
        carbon_factor_kg_co2_per_kg=0.5,
    )
    db_session.add_all([pcr, pir])
    db_session.commit()

    assert isinstance(pcr, PcrMaterial)
    assert isinstance(pir, PirMaterial)
    assert not isinstance(pcr, PirMaterial)
    assert not isinstance(pir, PcrMaterial)
    # PCR alanı PIR'a hiç sızmamalı (ayrı sınıf, farklı öznitelik seti)
    assert not hasattr(pir, "contamination_level") or pir.contamination_level is None
    assert not hasattr(pcr, "source_process") or pcr.source_process is None


def test_polymorphic_query_returns_correct_subclass_transparently(db_session):
    """RecipeLayer.material_id gibi düz bir FK üzerinden Material sorgulandığında
    bile SQLAlchemy doğru alt sınıfı (PcrMaterial/PirMaterial) döner --
    optimization_service.py'nin hiçbir değişiklik yapmadan çalışmasının sebebi."""
    polymer = _polymer(db_session)
    db_session.add(
        PcrMaterial(
            polymer_id=polymer.id, name="Test PCR 2", material_type="pcr",
            food_contact_eligible=True, max_recommended_ratio_pct=50, cost_per_kg=30,
            carbon_factor_kg_co2_per_kg=0.6, contamination_level="orta",
        )
    )
    db_session.commit()

    fetched = db_session.query(Material).filter_by(name="Test PCR 2").one()
    assert isinstance(fetched, PcrMaterial)
    assert fetched.contamination_level == "orta"


def test_pcr_content_never_counted_as_pir_and_vice_versa_at_material_type_level(db_session):
    """PPWR Md.7 hesabının (scorer._regulatory_margin_score) dayandığı temel
    sözleşme: material_type 'pcr' ve 'regranul' hiçbir zaman aynı değeri
    almaz, birbirinin yerine geçmez."""
    polymer = _polymer(db_session)
    pcr = PcrMaterial(polymer_id=polymer.id, name="X PCR", material_type="pcr", food_contact_eligible=True, max_recommended_ratio_pct=50, cost_per_kg=1, carbon_factor_kg_co2_per_kg=1)
    pir = PirMaterial(polymer_id=polymer.id, name="X PIR", material_type="regranul", food_contact_eligible=False, max_recommended_ratio_pct=30, cost_per_kg=1, carbon_factor_kg_co2_per_kg=1)
    db_session.add_all([pcr, pir])
    db_session.commit()
    assert pcr.material_type != pir.material_type


# --- Karbon EF çözümleme ----------------------------------------------------

def test_resolve_carbon_ef_with_demo_placeholder(db_session):
    polymer = _polymer(db_session)
    ef = CarbonEmissionFactor(
        material_key="Test Virgin", ef_value=1.9, unit="kg_co2e_per_kg",
        source="DEMO/VARSAYIMSAL — kaynak yok", is_demo_placeholder=True,
    )
    db_session.add(ef)
    db_session.flush()
    material = Material(
        polymer_id=polymer.id, name="Test Virgin", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100, cost_per_kg=38,
        carbon_factor_kg_co2_per_kg=1.9, carbon_ef_id=ef.id,
    )
    db_session.add(material)
    db_session.commit()

    value, status, source = resolve_carbon_ef(material)
    assert value == 1.9
    assert status == TANIMLI_DEMO
    assert "DEMO" in source


def test_resolve_carbon_ef_with_real_sourced_ef(db_session):
    polymer = _polymer(db_session)
    ef = CarbonEmissionFactor(
        material_key="Test Real", ef_value=1.5, source="Ecoinvent 3.9, PP granule, EU-28",
        year=2023, geography="EU", version="3.9", is_demo_placeholder=False,
    )
    db_session.add(ef)
    db_session.flush()
    material = Material(
        polymer_id=polymer.id, name="Test Real", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100, cost_per_kg=38,
        carbon_factor_kg_co2_per_kg=0.0, carbon_ef_id=ef.id,
    )
    db_session.add(material)
    db_session.commit()

    value, status, source = resolve_carbon_ef(material)
    assert value == 1.5
    assert status == TANIMLI_GERCEK
    assert source == "Ecoinvent 3.9, PP granule, EU-28"


def test_resolve_carbon_ef_undefined_falls_back_to_legacy_value_but_status_is_honest(db_session):
    """EF hiç bağlı değilse (carbon_ef_id None) -- iç arithmetik çökmesin diye
    legacy sütuna düşülür, AMA durum dürüstçe 'tanimlanmadi' kalır. Asla
    'kaynaklı EF' gibi sunulmaz."""
    polymer = _polymer(db_session)
    material = Material(
        polymer_id=polymer.id, name="Test Undefined", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100, cost_per_kg=38,
        carbon_factor_kg_co2_per_kg=1.9,  # carbon_ef_id set edilmedi
    )
    db_session.add(material)
    db_session.commit()

    value, status, source = resolve_carbon_ef(material)
    assert value == 1.9  # arithmetik çökmüyor
    assert status == TANIMLANMADI
    assert source is None


def test_resolve_carbon_ef_handles_objects_without_carbon_ef_attribute():
    """Eski test mock'ları (SimpleNamespace) `.carbon_ef` özniteliğini hiç
    taşımayabilir -- resolve_carbon_ef bunu AttributeError ile değil, None
    muamelesiyle karşılamalı."""
    from types import SimpleNamespace

    mock = SimpleNamespace(carbon_factor_kg_co2_per_kg=2.0)
    value, status, source = resolve_carbon_ef(mock)
    assert value == 2.0
    assert status == TANIMLANMADI
    assert source is None


def test_worst_status_priority_order():
    assert worst_status([TANIMLI_GERCEK, TANIMLI_DEMO]) == TANIMLI_DEMO
    assert worst_status([TANIMLI_GERCEK, TANIMLANMADI]) == TANIMLANMADI
    assert worst_status([TANIMLI_GERCEK, TANIMLI_GERCEK]) == TANIMLI_GERCEK
    assert worst_status([]) == TANIMLANMADI
