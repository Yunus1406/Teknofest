"""Faz J.0 — Madde 11 Doğrulaması. `EvaluationTier`'ın 3 seviyesi (Kesin
Teknik Kısıt / Malzeme-Proses Kısıtı / Tahmini Fiziksel Performans) gerçekten
kurulu ve doğru kullanılıyor mu? Bulunan gerçek boşluk: `_eliminated_summary`
tier bilgisini düşürüyordu -- artık `notable_eliminated`'in her gerekçesi
kendi GERÇEK tier'ını taşıyor (Dashboard 6'nın Kesin Teknik Kısıt ile
Malzeme-Proses Kısıtı'nı yapısal olarak ayırt edebilmesi için)."""
from app.constraint_engine.engine import evaluate_candidate
from app.constraint_engine.types import (
    EvaluationContext,
    EvaluationTier,
    LayerCandidate,
    LineSpec,
    MaterialSpec,
    PackagingContext,
    RecipeCandidate,
)
from app.knowledge_base.loader import load_all
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
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
        db.add(LineMaterialCompatibility(line_id=line.id, material_id=material_ids[name], max_ratio_pct=ratio))
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


def test_notable_eliminated_reasons_carry_real_evaluation_tier(db_session):
    """Her `notable_eliminated` girdisinin `reasons` listesindeki her
    gerekçe, GERÇEK bir EvaluationTier değeri taşımalı (kesin_teknik_kisit
    ya da malzeme_proses_kisiti) -- uydurma/varsayılan bir değer değil."""
    req, line = _seed_tabak_line_and_request(db_session)

    result = optimization_service.run_optimization(db_session, req.id, line.id, ratio_step_pct=10)

    assert len(result["notable_eliminated"]) > 0
    seen_tiers: set[str] = set()
    for item in result["notable_eliminated"]:
        assert len(item["reasons"]) > 0
        for reason in item["reasons"]:
            assert "tier" in reason
            assert "text" in reason
            assert reason["tier"] in (EvaluationTier.KESIN_TEKNIK_KISIT, EvaluationTier.MALZEME_PROSES_KISITI)
            seen_tiers.add(reason["tier"])
    # MAX_NOTABLE_ELIMINATED örneklemesi tüm eleme türlerini garanti etmez
    # (sadece ilk birkaç öne çıkan örnek) -- burada asıl kanıtlanan, tier
    # bilgisinin GERÇEKTEN taşındığı ve uydurma bir değere düşülmediği.
    assert seen_tiers.issubset({EvaluationTier.KESIN_TEKNIK_KISIT, EvaluationTier.MALZEME_PROSES_KISITI})


def _material(id_="mat-1", max_ratio=100.0):
    return MaterialSpec(
        id=id_, name="Test Malzeme", polymer_code="PE", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=max_ratio,
        degradation_factor=0.0, mfi_g_10min=None, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,
    )


def _line(material_max_ratio: dict, min_micron=20.0, max_micron=100.0):
    return LineSpec(
        id="line-1", name="Test Hat", layer_structure="A", layer_count=1,
        min_micron=min_micron, max_micron=max_micron, min_gsm=None, max_gsm=None,
        supported_packaging_types=[], material_max_ratio=material_max_ratio,
    )


def _ctx(line: LineSpec) -> EvaluationContext:
    return EvaluationContext(
        packaging=PackagingContext(packaging_type="esnek film ambalaj", food_contact=False, target_volume_units=1000),
        line=line, regulations=[],
    )


def test_kesin_teknik_kisit_genuinely_reachable():
    """Toplam kalınlık hattın aralığı dışındaysa -- KESIN_TEKNIK_KISIT."""
    material = _material()
    candidate = RecipeCandidate(layers=[LayerCandidate(layer_index=0, layer_label="A", material=material, ratio_pct=100.0, thickness_micron=500.0)])
    line = _line(material_max_ratio={material.id: 100.0}, min_micron=20.0, max_micron=100.0)

    check = evaluate_candidate(candidate, _ctx(line))

    assert check.eliminated is True
    assert any(v.tier == EvaluationTier.KESIN_TEKNIK_KISIT for v in check.violations)


def test_malzeme_proses_kisiti_genuinely_reachable():
    """Malzeme hatta hiç tanımlı değilse (material_max_ratio'da yoksa) --
    MALZEME_PROSES_KISITI."""
    material = _material()
    candidate = RecipeCandidate(layers=[LayerCandidate(layer_index=0, layer_label="A", material=material, ratio_pct=100.0, thickness_micron=50.0)])
    line = _line(material_max_ratio={}, min_micron=20.0, max_micron=100.0)  # malzeme hatta hiç tanımlı değil

    check = evaluate_candidate(candidate, _ctx(line))

    assert check.eliminated is True
    assert any(v.tier == EvaluationTier.MALZEME_PROSES_KISITI for v in check.violations)


def test_finalist_evaluation_never_claims_verified_before_production():
    """Aşama 7'nin (üretilmemiş) finalist adayları için yazdığı
    RecipeEvaluation'ın tier'ı HER ZAMAN TAHMINI_FIZIKSEL_PERFORMANS'tır ve
    reason_text'i asla 'doğrulandı' iddiası taşımaz -- optimization_
    service.py::_persist_finalist'in ürettiği metni statik olarak denetler."""
    import inspect

    from app.services import optimization_service as svc

    source = inspect.getsource(svc._persist_finalist)
    assert "EvaluationTier.TAHMINI_FIZIKSEL_PERFORMANS" in source
    assert "data_confidence=score.data_confidence" in source
    assert "doğrulandı" not in source
