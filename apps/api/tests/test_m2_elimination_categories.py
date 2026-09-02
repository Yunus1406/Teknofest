"""Faz M.2 (Madde 12) — huni görselleştirmesinin yanında eleme nedenlerinin
kategorik dağılımı ("294 eleme: 180 malzeme uyumsuzluğu, 74 mevzuat, 40
makine kısıtı"). `notable_eliminated`'in 3 örneğinden BAĞIMSIZ, TÜM elenen
adaylar sayılmalı; toplam her zaman elenen aday sayısına eşit olmalı (ihlal
sayısına değil)."""
from app.constraint_engine.rules import categorize_eliminations
from app.constraint_engine.types import EvaluationResult, EvaluationTier, EvaluationVerdict
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest
from app.services import optimization_service


def _violation(reason_code: str, tier: str = EvaluationTier.MALZEME_PROSES_KISITI) -> EvaluationResult:
    return EvaluationResult(tier=tier, verdict=EvaluationVerdict.ELENDI, reason_code=reason_code, reason_text="test")


def test_categorize_eliminations_counts_one_category_per_candidate_not_per_violation():
    """Toplam, elenen aday SAYISINA eşit olmalı -- ihlal sayısına değil.
    Bir adayın İKİ ihlali olsa bile (malzeme + mevzuat), sadece İLK
    ihlalinin kategorisi sayılır."""
    eliminated = [
        ("candidate1", [_violation("hat_malzeme_eslesmiyor"), _violation("gida_temasi_uygun_degil")]),
        ("candidate2", [_violation("gida_temasi_uygun_degil")]),
        ("candidate3", [_violation("micron_disi", EvaluationTier.KESIN_TEKNIK_KISIT)]),
    ]
    counts = categorize_eliminations(eliminated)
    assert sum(counts.values()) == 3  # 3 aday, 4 ihlal DEĞİL
    assert counts["malzeme_uyumsuzlugu"] == 1  # candidate1 -- ilk ihlali malzeme
    assert counts["mevzuat"] == 1  # candidate2
    assert counts["makine_hat_kisiti"] == 1  # candidate3


def test_categorize_eliminations_unknown_reason_code_falls_into_diger():
    eliminated = [("c1", [_violation("bilinmeyen_yeni_kural")])]
    counts = categorize_eliminations(eliminated)
    assert counts["diger"] == 1


def test_categorize_eliminations_empty_list_returns_zero_counts():
    counts = categorize_eliminations([])
    assert sum(counts.values()) == 0
    assert set(counts.keys()) == {
        "malzeme_uyumsuzlugu", "mevzuat", "makine_hat_kisiti", "gecmis_basarisizlik", "diger",
    }


# --- Entegrasyon: run_optimization() gerçekten dolduruyor mu ---------------

def test_run_optimization_elimination_category_counts_sum_matches_eliminated_count(db_session):
    db = db_session
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    virgin = Material(
        polymer_id=polymer.id, name="PE Virgin M2", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )
    pcr = Material(
        polymer_id=polymer.id, name="PE PCR M2", material_type="pcr",
        food_contact_eligible=True, max_recommended_ratio_pct=40.0, cost_per_kg=20.0,
        carbon_factor_kg_co2_per_kg=0.6,
    )
    db.add_all([virgin, pcr])
    db.flush()
    line = ProductionLine(
        name="Test Hat M2", layer_structure="A/B/A", layer_count=3, min_micron=50, max_micron=90,
        supported_packaging_types=["esnek_film_ambalaj"],
    )
    db.add(line)
    db.flush()
    db.add(LineMaterialCompatibility(line_id=line.id, material_id=pcr.id, max_ratio_pct=40.0))
    db.add(LineMaterialCompatibility(line_id=line.id, material_id=virgin.id, max_ratio_pct=100.0))
    db.commit()

    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    result = optimization_service.run_optimization(db, req.id, line.id, ratio_step_pct=10)

    eliminated_count = result["generated_candidate_count"] - result["survived_constraint_engine_count"]
    counts = result["elimination_category_counts"]
    assert set(counts.keys()) == {
        "malzeme_uyumsuzlugu", "mevzuat", "makine_hat_kisiti", "gecmis_basarisizlik", "diger",
    }
    assert sum(counts.values()) == eliminated_count


def test_run_endpoint_persists_and_returns_elimination_category_counts(db_session):
    """OptimizationRun.parameters'a yazılan değer, GET /runs/{id} ile AYNI
    şekilde geri okunabilmeli (Faz C.4'ün notable_eliminated kalıcılığıyla
    aynı desen)."""
    from app.models.optimization import OptimizationRun

    db = db_session
    polymer = Polymer(code="PP", name="Polipropilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    virgin = Material(
        polymer_id=polymer.id, name="PP Virgin M2", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=38.0,
        carbon_factor_kg_co2_per_kg=1.9,
    )
    db.add(virgin)
    db.flush()
    line = ProductionLine(
        name="Test Hat M2b", layer_structure="A", layer_count=1, min_micron=50, max_micron=90,
        supported_packaging_types=["plastik_tabak"],
    )
    db.add(line)
    db.flush()
    db.add(LineMaterialCompatibility(line_id=line.id, material_id=virgin.id, max_ratio_pct=100.0))
    db.commit()

    req = PackagingRequest(
        packaging_type="plastik tabak", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    result = optimization_service.run_optimization(db, req.id, line.id, ratio_step_pct=10)
    run = db.get(OptimizationRun, result["run"].id)
    assert run.parameters["elimination_category_counts"] == result["elimination_category_counts"]
