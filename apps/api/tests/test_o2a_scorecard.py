"""Faz O.2 (Madde 19) — Sürdürülebilirlik Karnesi. Her boyut mevcut gerçek
veriden (comparison/executive_summary/regulatory_assessments/gıda teması
kanıt listesi) türetilir; yeni bir hesap YOK. Referans yoksa karşılaştırma
yüzdesi uydurulmaz (Faz A kuralı)."""
from app.models.knowledge import Material, Polymer, Regulation
from app.models.production import SustainabilityResult
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer, RecipeMetric, RegulatoryAssessment
from app.services.production_flow_service import build_comparison
from app.services.report_service import build_executive_summary
from app.services.scorecard_service import build_sustainability_scorecard


def _material(db, name="Test Malzeme O2a"):
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


def _verified_recipe(db, material, packaging_type="esnek film ambalaj", version=1, food_contact=True):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test ürün", target_market="AB",
        food_contact=food_contact, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=version, source="sistem_uretti", status="dogrulandi",
        is_verified=True, total_micron=70.0,
    )
    db.add(recipe)
    db.flush()
    db.add(
        RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0)
    )
    db.commit()
    db.refresh(recipe)
    return recipe


def _add_metrics(db, recipe, virgin_pct=80.0, pcr_pct=20.0, regranul_pct=0.0, carbon=1.8, cost=30.0):
    for metric_type, value, unit in [
        ("virgin_kullanimi", virgin_pct, "%"), ("pcr_kullanimi", pcr_pct, "%"),
        ("regranul_kullanimi", regranul_pct, "%"), ("karbon", carbon, "kg_co2/kg"), ("maliyet", cost, "TL/kg"),
    ]:
        db.add(RecipeMetric(recipe_id=recipe.id, metric_type=metric_type, value=value, unit=unit, is_estimated=True, data_source_type="hesaplanan"))
    db.commit()


def _add_sustainability_result(db, recipe, **overrides):
    per_1000 = {
        "virgin_kg": 8.0, "pcr_kg": 2.0, "regranul_kg": 0.0, "karbon_kg_co2": 20.0,
        "karbon_veri_kalitesi": "tanimli_demo", "fire_kg": 1.0, "enerji_kwh": 5.0,
        "fire_enerji_veri_kaynagi": "simulasyon_verisi",
    }
    per_1000.update(overrides)
    db.add(SustainabilityResult(recipe_id=recipe.id, per_1000_units=per_1000, is_actual=True))
    db.commit()


def _scorecard(db, recipe):
    comparison = build_comparison(db, recipe)
    executive_summary = build_executive_summary(db, recipe, comparison)
    return build_sustainability_scorecard(db, recipe, comparison, executive_summary)


def _dim(scorecard, key):
    return next(d for d in scorecard["dimensions"] if d["key"] == key)


def test_has_all_9_dimensions_in_order(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    scorecard = _scorecard(db_session, recipe)

    assert [d["key"] for d in scorecard["dimensions"]] == [
        "malzeme_verimliligi", "dongusellik", "virgin_azaltimi", "pcr_kullanimi",
        "karbon_performansi", "enerji_performansi", "fire_performansi",
        "mevzuat_hazirligi", "kanit_tamamlanma",
    ]


def test_no_reference_shows_absolute_not_fabricated_comparison(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    scorecard = _scorecard(db_session, recipe)

    virgin = _dim(scorecard, "virgin_azaltimi")
    assert virgin["has_reference"] is False
    assert virgin["karsilastirma_pct"] is None
    assert virgin["deger"] == 80.0

    karbon = _dim(scorecard, "karbon_performansi")
    assert karbon["has_reference"] is False
    assert karbon["karsilastirma_pct"] is None
    assert karbon["deger"] == 20.0
    assert karbon["veri_guveni_kind"] == "tanimli_demo"


def test_with_reference_shows_real_reduction_pct(db_session):
    material = _material(db_session)
    ref_recipe = _verified_recipe(db_session, material, version=1)
    _add_metrics(db_session, ref_recipe, virgin_pct=100.0, pcr_pct=10.0, carbon=2.0)
    _add_sustainability_result(db_session, ref_recipe, karbon_kg_co2=25.0)

    new_recipe = _verified_recipe(db_session, material, version=2)
    _add_metrics(db_session, new_recipe, virgin_pct=80.0, pcr_pct=20.0, carbon=1.6)
    _add_sustainability_result(db_session, new_recipe, karbon_kg_co2=20.0)

    scorecard = _scorecard(db_session, new_recipe)

    virgin = _dim(scorecard, "virgin_azaltimi")
    assert virgin["has_reference"] is True
    assert virgin["karsilastirma_pct"] == 20.0  # (100-80)/100*100

    pcr = _dim(scorecard, "pcr_kullanimi")
    assert pcr["has_reference"] is True
    assert pcr["karsilastirma_pct"] is not None

    karbon = _dim(scorecard, "karbon_performansi")
    assert karbon["karsilastirma_pct"] == 20.0  # (25-20)/25*100


def test_malzeme_verimliligi_computed_from_real_mass(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe, virgin_kg=8.0, pcr_kg=2.0, regranul_kg=0.0, fire_kg=1.0)

    scorecard = _scorecard(db_session, recipe)
    dim = _dim(scorecard, "malzeme_verimliligi")
    assert dim["deger"] == round((10.0 / 11.0) * 100, 1)
    assert dim["veri_guveni_kind"] == "simulasyon_verisi"


def test_malzeme_verimliligi_none_when_not_yet_produced(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)

    scorecard = _scorecard(db_session, recipe)
    dim = _dim(scorecard, "malzeme_verimliligi")
    assert dim["deger"] is None
    assert dim["durum_metni"] == "henuz_uretilmedi"


def test_dongusellik_uses_ppwr_art6_assessment_verdict(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    reg = Regulation(code="PPWR-ART-6", title="Geri Dönüştürülebilirlik", category="geri_donusturulebilirlik", description="test")
    db_session.add(reg)
    db_session.flush()
    db_session.add(
        RegulatoryAssessment(
            packaging_request_id=recipe.packaging_request_id, regulation_id=reg.id,
            verdict="uygun_gorunuyor", reasoning="test",
        )
    )
    db_session.commit()

    scorecard = _scorecard(db_session, recipe)
    dim = _dim(scorecard, "dongusellik")
    assert dim["durum_metni"] == "uygun_gorunuyor"
    assert dim["veri_guveni_kind"] == "mevzuat"


def test_dongusellik_no_assessment_means_degerlendirilmedi(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    scorecard = _scorecard(db_session, recipe)
    dim = _dim(scorecard, "dongusellik")
    assert dim["durum_metni"] == "degerlendirilmedi"


def test_mevzuat_hazirligi_counts_real_verdicts(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    reg1 = Regulation(code="X-1", title="t1", category="c", description="d")
    reg2 = Regulation(code="X-2", title="t2", category="c", description="d")
    db_session.add_all([reg1, reg2])
    db_session.flush()
    db_session.add_all([
        RegulatoryAssessment(packaging_request_id=recipe.packaging_request_id, regulation_id=reg1.id, verdict="uygun_gorunuyor", reasoning="r1"),
        RegulatoryAssessment(packaging_request_id=recipe.packaging_request_id, regulation_id=reg2.id, verdict="inceleme_gerekli", reasoning="r2"),
    ])
    db_session.commit()

    scorecard = _scorecard(db_session, recipe)
    dim = _dim(scorecard, "mevzuat_hazirligi")
    assert dim["deger"] == 50.0
    assert dim["durum_metni"] == "1/2 madde uygun görünüyor"


def test_kanit_tamamlanma_gida_temasi_yok(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material, food_contact=False)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    scorecard = _scorecard(db_session, recipe)
    dim = _dim(scorecard, "kanit_tamamlanma")
    assert dim["durum_metni"] == "gida_temasi_yok"
    assert dim["deger"] is None


def test_kanit_tamamlanma_gida_temasi_var_hepsi_eksik(db_session):
    material = _material(db_session)
    recipe = _verified_recipe(db_session, material, food_contact=True)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    scorecard = _scorecard(db_session, recipe)
    dim = _dim(scorecard, "kanit_tamamlanma")
    assert dim["deger"] == 0.0
    assert dim["durum_metni"] is not None
