"""Faz C.4 — `OptimizationRun.notable_eliminated`'ın kalıcı hale getirildiğini
doğrular. Fixture, `scripts/seed_demo.py`'deki tabak hattı/hammadde
kurulumunun aynısını kullanır (bkz. o script) çünkü bu senaryo GERÇEKTEN
hem hayatta kalan hem elenen aday üretiyor (729 aday / 486 hayatta / 3
gösterilen eleme — seed script konsol çıktısıyla doğrulanmış); rastgele
küçültülmüş bir fixture ile aynı garantiyi vermek güvenilir olmazdı."""
from app.knowledge_base.loader import load_all
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
from app.models.optimization import OptimizationRun
from app.models.recipe import PackagingRequest
from app.services import optimization_service


def _seed_tabak_line_and_request(db):
    ids = load_all(db)
    material_ids = ids["materials"]

    line = ProductionLine(
        name="Test Hat-1 - Termoform Tabak Hattı", process_type="Thermoforming",
        extruder_count=2, layer_structure="A/B/A", layer_count=3,
        min_micron=300, max_micron=900, max_width_mm=800,
        min_dosage_pct=0, max_dosage_pct=50, line_speed_m_min=25,
        supported_packaging_types=["plastik_tabak"], energy_kwh_per_kg=0.45, active=True,
    )
    db.add(line)
    db.flush()

    tabak_materials = [
        ("PP Virgin Enjeksiyon Sınıfı", 100),
        ("PP PCR Gıda Sınıfı (Dekontaminasyonlu)", 50),
        ("PP Regranül (Post-Endüstriyel)", 30),
        ("PET Virgin Şişe/Tabak Sınıfı", 100),
        ("rPET Gıda Sınıfı (Dekontaminasyonlu)", 70),
        ("PET Regranül (Endüstriyel)", 20),
        ("PS Virgin", 100),
        ("PS Regranül (Post-Endüstriyel)", 20),
    ]
    for name, ratio in tabak_materials:
        db.add(
            LineMaterialCompatibility(line_id=line.id, material_id=material_ids[name], max_ratio_pct=ratio)
        )
    db.commit()

    req = PackagingRequest(
        packaging_type="plastik tabak", usage_area="gıda servisi (yemek tabağı)",
        product="tek kullanımlık yemek tabağı", target_market="AB", food_contact=True,
        target_volume_units=500_000, dimensions={"length_mm": 230, "width_mm": 230, "height_mm": 20},
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req, line


def test_notable_eliminated_persisted_matches_returned_value(db_session):
    req, line = _seed_tabak_line_and_request(db_session)

    result = optimization_service.run_optimization(db_session, req.id, line.id, ratio_step_pct=10)

    run = db_session.get(OptimizationRun, result["run"].id)
    db_session.refresh(run)

    assert len(result["notable_eliminated"]) > 0, "Bu senaryo gerçek eleme üretmeli (seed_demo ile aynı kurulum)"
    assert run.notable_eliminated == result["notable_eliminated"]
    for item in run.notable_eliminated:
        assert "composition_summary" in item
        assert "reasons" in item
        assert "summary_text" in item


def test_old_runs_without_notable_eliminated_read_back_as_empty_list(db_session):
    """Migration öncesi (bu sütun eklenmeden önceki) satırları simüle eder:
    ORM seviyesinde satır oluşturulurken alan hiç set edilmese bile model
    varsayılanı (`default=list`) sayesinde boş liste ile güvenle okunur."""
    req, line = _seed_tabak_line_and_request(db_session)
    run = OptimizationRun(packaging_request_id=req.id, parameters={})
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    assert run.notable_eliminated == []
