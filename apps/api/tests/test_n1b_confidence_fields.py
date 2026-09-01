"""Faz N.1b (Madde 14) — Aşama 3'ün mevzuat kategori kararı (Faz L.1'in karar
ağacı çıktısı) ve Aşama 4'ün hat uygunluk skoru (Faz K.4) için Veri Güveni
alanları. İkisi de additive -- mevcut hiçbir alan/davranış değişmedi."""
from app.knowledge_base.loader import load_all
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest
from app.services.packaging_service import assess_regulations, match_infrastructure


def _request(db, packaging_type="plastik tabak", target_thickness_micron=None):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test n1b", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 200, "width_mm": 200},
        target_thickness_micron=target_thickness_micron,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_decision_trail_material_guess_always_marked_dusuk(db_session):
    load_all(db_session)
    req = _request(db_session)

    overall, assessments = assess_regulations(db_session, req)

    assert len(assessments) > 0
    for a in assessments:
        assert a.decision_trail["ambalaj_malzemesi_guveni"] == "dusuk"


def _line_and_material(db, min_micron=20.0, max_micron=120.0):
    polymer = Polymer(code="PP", name="Polipropilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    material = Material(
        polymer_id=polymer.id, name="PP Virgin N1b", material_type="virgin", density_g_cm3=0.905,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
    )
    db.add(material)
    db.flush()
    line = ProductionLine(
        name="Test Hat N1b", process_type="Termoform", layer_structure="A", layer_count=1,
        min_micron=min_micron, max_micron=max_micron, supported_packaging_types=["plastik_tabak"],
    )
    db.add(line)
    db.flush()
    db.add(LineMaterialCompatibility(line_id=line.id, material_id=material.id, max_ratio_pct=100.0))
    db.commit()
    return line, material


def test_mikron_confidence_varsayimsal_when_no_target_thickness(db_session):
    _line_and_material(db_session)
    req = _request(db_session, target_thickness_micron=None)

    results = match_infrastructure(db_session, req)

    assert len(results) > 0
    for r in results:
        assert r["mikron_araligi_veri_guveni"] == "varsayimsal"


def test_mikron_confidence_yuksek_when_target_thickness_set(db_session):
    _line_and_material(db_session)
    req = _request(db_session, target_thickness_micron=70.0)

    results = match_infrastructure(db_session, req)

    assert len(results) > 0
    for r in results:
        assert r["mikron_araligi_veri_guveni"] == "yuksek"
