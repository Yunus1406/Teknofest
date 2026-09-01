"""Faz M.3 (Madde 13) — optimizasyon 0 uygun aday ürettiğinde sistem artık
"aday bulunamadı" demekle yetinmiyor: hangi kısıtın TÜM adayları elediğini
ve (varsa) K.4'ün hat uygunluk matrisinden somut bir alternatif hat önerisini
gösteren bir teşhis üretiyor."""
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest
from app.services import optimization_service


def _polymer_and_material(db, code, name_suffix):
    polymer = Polymer(code=code, name=code, category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    m = Material(
        polymer_id=polymer.id, name=f"{code} Virgin {name_suffix}", material_type="virgin",
        density_g_cm3=0.92, degradation_factor=0.0, food_contact_eligible=True,
        max_recommended_ratio_pct=100.0, cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_zero_finalists_diagnosis_identifies_dominant_reason_and_alternative_line(db_session):
    db = db_session
    material = _polymer_and_material(db, "PE", "M3")

    # Seçili hat: malzeme uyumlu (candidate ÜRETİLEBİLİR) ama
    # supported_packaging_types BOŞ -- TÜM adaylar "ambalaj_turu_
    # desteklenmiyor" (KESIN_TEKNIK_KISIT) ile elenecek.
    selected_line = ProductionLine(
        name="Seçili Hat M3", process_type="Blown Film", layer_structure="A", layer_count=1,
        min_micron=10.0, max_micron=200.0, supported_packaging_types=[],
    )
    db.add(selected_line)
    db.flush()
    db.add(LineMaterialCompatibility(line_id=selected_line.id, material_id=material.id, max_ratio_pct=100.0))

    # Alternatif hat: AYNI malzeme uyumlu + doğru ambalaj türünü destekliyor
    # -- match_infrastructure'da eligible=True olmalı, teşhis bunu önermeli.
    alt_line = ProductionLine(
        name="Alternatif Hat M3", process_type="Blown Film", layer_structure="A", layer_count=1,
        min_micron=10.0, max_micron=200.0, supported_packaging_types=["esnek_film_ambalaj"],
    )
    db.add(alt_line)
    db.flush()
    db.add(LineMaterialCompatibility(line_id=alt_line.id, material_id=material.id, max_ratio_pct=100.0))
    db.commit()

    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test m3", product="test", target_market="AB",
        food_contact=False, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    result = optimization_service.run_optimization(db, req.id, selected_line.id, ratio_step_pct=10)

    assert result["survived_constraint_engine_count"] == 0
    assert len(result["finalist_candidate_ids"]) == 0
    diagnosis = result["diagnosis"]
    assert diagnosis is not None
    assert diagnosis["dominant_reason_code"] == "ambalaj_turu_desteklenmiyor"
    assert diagnosis["affected_pct"] == 100
    assert diagnosis["alternative_line_name"] == "Alternatif Hat M3"
    assert diagnosis["alternative_line_score_pct"] is not None
    assert "Alternatif Hat M3" in diagnosis["suggestion_text"]
    assert "Seçili Hat M3" in diagnosis["suggestion_text"]


def test_diagnosis_is_none_when_finalists_exist(db_session):
    """Regresyon kilidi: normal (>0 finalist) bir koşuda diagnosis HER ZAMAN
    None kalmalı -- mevcut davranış hiç değişmemeli."""
    db = db_session
    polymer = Polymer(code="PP", name="Polipropilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    material = Material(
        polymer_id=polymer.id, name="PP Virgin M3b", material_type="virgin", density_g_cm3=0.905,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=38.0, carbon_factor_kg_co2_per_kg=1.9,
    )
    db.add(material)
    db.flush()
    line = ProductionLine(
        name="Normal Hat M3", process_type="Thermoforming", layer_structure="A", layer_count=1,
        min_micron=10.0, max_micron=200.0, supported_packaging_types=["plastik_tabak"],
    )
    db.add(line)
    db.flush()
    db.add(LineMaterialCompatibility(line_id=line.id, material_id=material.id, max_ratio_pct=100.0))
    db.commit()

    req = PackagingRequest(
        packaging_type="plastik tabak", usage_area="test m3b", product="test", target_market="AB",
        food_contact=False, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    result = optimization_service.run_optimization(db, req.id, line.id, ratio_step_pct=10)

    assert len(result["finalist_candidate_ids"]) > 0
    assert result["diagnosis"] is None


def test_run_endpoint_persists_diagnosis_in_parameters(db_session):
    from app.models.optimization import OptimizationRun

    db = db_session
    material = _polymer_and_material(db, "PE", "M3c")
    line = ProductionLine(
        name="Seçili Hat M3c", process_type="Blown Film", layer_structure="A", layer_count=1,
        min_micron=10.0, max_micron=200.0, supported_packaging_types=[],
    )
    db.add(line)
    db.flush()
    db.add(LineMaterialCompatibility(line_id=line.id, material_id=material.id, max_ratio_pct=100.0))
    db.commit()

    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test m3c", product="test", target_market="AB",
        food_contact=False, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    result = optimization_service.run_optimization(db, req.id, line.id, ratio_step_pct=10)
    run = db.get(OptimizationRun, result["run"].id)
    assert run.parameters["diagnosis"] == result["diagnosis"]
