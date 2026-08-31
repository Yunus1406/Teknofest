"""Faz H.6 — Optimizasyon Raporuna 5 ek bölüm (Hesaplama Metodolojisi,
Kaynakça, Veri Kalitesi/Belirsizlik, Kullanılan Varsayımlar, Veri Kaynağı
Matrisi). Mevcut 16 anahtarın hiçbirinin kaldırılmadığını, yeni bölümlerin
GERÇEK veriden (yeniden sorgu değil, önceden inşa edilmiş bölümlerden)
derlendiğini ve PDF'in hatasız üretildiğini doğrular."""
from app.models.knowledge import CarbonEmissionFactor, Material, Polymer
from app.models.production import SustainabilityResult
from app.models.recipe import PackagingRequest, Recipe, RecipeEvaluation, RecipeLayer, RecipeMetric
from app.services import pdf_service
from app.services.report_service import build_optimization_report_data


def _material_with_demo_ef(db, name="Test Malzeme Demo EF"):
    polymer = db.query(Polymer).filter_by(code="PE").one_or_none()
    if polymer is None:
        polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
        db.add(polymer)
        db.flush()
    ef = CarbonEmissionFactor(
        material_key=name, factor_type="malzeme", ef_value=1.8, unit="kg_co2e_per_kg",
        source="DEMO/VARSAYIMSAL — kaynak yok", year=None, version="1.0", is_demo_placeholder=True,
    )
    db.add(ef)
    db.flush()
    material = Material(
        polymer_id=polymer.id, name=name, material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8, carbon_ef_id=ef.id,
    )
    db.add(material)
    db.flush()
    return material


def _verified_recipe(db, material, packaging_type="esnek film ambalaj", version=1, thickness=70.0):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test ürün", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=version, source="sistem_uretti", status="dogrulandi",
        is_verified=True, total_micron=thickness,
    )
    db.add(recipe)
    db.flush()
    db.add(
        RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=thickness)
    )
    db.commit()
    db.refresh(recipe)
    return recipe


def _add_sustainability_result(db, recipe, **overrides):
    per_1000 = {
        "virgin_kg": 10.0, "pcr_kg": 2.0, "regranul_kg": 0.0, "karbon_kg_co2": 20.0,
        "karbon_veri_kalitesi": "tanimli_demo", "fire_kg": 1.0, "enerji_kwh": 5.0,
        "kutle_veri_kaynagi": "hesaplanan", "fire_enerji_veri_kaynagi": "simulasyon_verisi",
    }
    per_1000.update(overrides)
    db.add(SustainabilityResult(recipe_id=recipe.id, per_1000_units=per_1000, is_actual=True))
    db.commit()


def _add_metrics(db, recipe, virgin_pct=100.0, pcr_pct=0.0, regranul_pct=0.0, carbon=1.8, cost=30.0):
    for metric_type, value, unit in [
        ("virgin_kullanimi", virgin_pct, "%"), ("pcr_kullanimi", pcr_pct, "%"),
        ("regranul_kullanimi", regranul_pct, "%"), ("karbon", carbon, "kg_co2/kg"), ("maliyet", cost, "TL/kg"),
    ]:
        db.add(RecipeMetric(recipe_id=recipe.id, metric_type=metric_type, value=value, unit=unit, is_estimated=True, data_source_type="hesaplanan"))
    db.commit()


def test_all_5_new_sections_present(db_session):
    material = _material_with_demo_ef(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    for key in ["hesaplama_metodolojisi", "kaynakca", "veri_kalitesi_notu", "kullanilan_varsayimlar", "veri_kaynagi_matrisi"]:
        assert key in data


def test_existing_16_keys_unchanged(db_session):
    material = _material_with_demo_ef(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    original_keys = [
        "kapak", "yonetici_ozeti", "ambalaj_bilgileri", "referans_recete", "optimizasyon_sureci",
        "neden_elendi", "secilen_recete", "tahmini_sonuclar", "gercek_uretim_sonuclari",
        "fiziksel_dogrulama", "surdurulebilirlik_performansi", "ppwr_on_uyum", "iklim_dongusellik",
        "veri_izlenebilirligi", "recete_izlenebilirligi", "sonuc",
    ]
    for key in original_keys:
        assert key in data


def test_methodology_mentions_mass_balance_and_carbon(db_session):
    material = _material_with_demo_ef(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    text = data["hesaplama_metodolojisi"]["aciklama"]
    assert "Kütle Dengesi" in text
    assert "Karbon" in text
    assert "Optimizasyon Skoru" in text


def test_bibliography_reuses_data_traceability_carbon_sources(db_session):
    material = _material_with_demo_ef(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["kaynakca"]["karbon_ef_kaynaklari"] == data["veri_izlenebilirligi"]["carbon_ef_sources"]
    assert len(data["kaynakca"]["karbon_ef_kaynaklari"]) == 1
    assert data["kaynakca"]["karbon_ef_kaynaklari"][0]["material_name"] == material.name


def test_assumptions_lists_demo_placeholder_ef_when_present(db_session):
    material = _material_with_demo_ef(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["kullanilan_varsayimlar"]["has_assumptions"] is True
    assert any(material.name in item for item in data["kullanilan_varsayimlar"]["items"])


def test_assumptions_empty_when_no_demo_ef_and_no_carbon_result(db_session):
    """Karbon EF hiç bağlı değilse (TANIMLANMADI, DEMO bile değil) ve
    per_1000'de karbon_veri_kalitesi de yoksa, varsayım listesi boş
    kalmalı -- uydurma bir varsayım eklenmez."""
    polymer = Polymer(code="PP", name="Polipropilen", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()
    material = Material(
        polymer_id=polymer.id, name="EF'siz Malzeme", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8,  # carbon_ef_id YOK
    )
    db_session.add(material)
    db_session.flush()
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    db_session.add(SustainabilityResult(recipe_id=recipe.id, per_1000_units={"virgin_kg": 5.0}, is_actual=True))
    db_session.commit()

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["kullanilan_varsayimlar"]["has_assumptions"] is False
    assert data["kullanilan_varsayimlar"]["items"] == []


def test_data_quality_reflects_recipe_evaluation_confidence(db_session):
    material = _material_with_demo_ef(db_session)
    recipe = _verified_recipe(db_session, material)
    _add_metrics(db_session, recipe)
    _add_sustainability_result(db_session, recipe)
    db_session.add(RecipeEvaluation(recipe_id=recipe.id, tier="tahmini_fiziksel_performans", verdict="gecti", reason_code="x", reason_text="x", data_confidence="orta"))
    db_session.add(RecipeEvaluation(recipe_id=recipe.id, tier="tahmini_fiziksel_performans", verdict="gecti", reason_code="x", reason_text="x", data_confidence="orta"))
    db_session.commit()

    data = build_optimization_report_data(db_session, recipe.id)

    assert data["veri_kalitesi_notu"]["data_confidence_dagilimi"] == {"orta": 2}
    assert data["veri_kalitesi_notu"]["karbon_veri_kalitesi"] == "tanimli_demo"
    assert data["veri_kalitesi_notu"]["demo_varsayimsal_ef_sayisi"] == 1
    assert data["veri_kalitesi_notu"]["toplam_karbon_ef_sayisi"] == 1


def test_source_matrix_contains_expected_entries(db_session):
    material = _material_with_demo_ef(db_session)
    old_recipe = _verified_recipe(db_session, material, version=1)
    _add_metrics(db_session, old_recipe)
    _add_sustainability_result(db_session, old_recipe)

    new_recipe = _verified_recipe(db_session, material, version=2)
    _add_metrics(db_session, new_recipe)
    _add_sustainability_result(db_session, new_recipe)

    data = build_optimization_report_data(db_session, new_recipe.id)

    matrix = data["veri_kaynagi_matrisi"]
    alanlar = {row["alan"] for row in matrix}
    assert "Referans Reçete" in alanlar
    assert "Seçilen Reçete (katman/kalınlık)" in alanlar
    assert "Tahmini Sonuçlar (Aşama 8)" in alanlar
    assert "Gerçekleşen Virgin/PCR/PIR-Regranül/Karbon" in alanlar
    assert "Gerçekleşen Fire/Enerji" in alanlar


def test_pdf_renders_21_sections_without_crash(db_session):
    material = _material_with_demo_ef(db_session)
    old_recipe = _verified_recipe(db_session, material, version=1)
    _add_metrics(db_session, old_recipe)
    _add_sustainability_result(db_session, old_recipe)

    new_recipe = _verified_recipe(db_session, material, version=2)
    _add_metrics(db_session, new_recipe)
    _add_sustainability_result(db_session, new_recipe)
    db_session.add(RecipeEvaluation(recipe_id=new_recipe.id, tier="tahmini_fiziksel_performans", verdict="gecti", reason_code="x", reason_text="x", data_confidence="yuksek"))
    db_session.commit()

    data = build_optimization_report_data(db_session, new_recipe.id)
    pdf_bytes = pdf_service.render_technical_report(data)

    assert pdf_bytes[:5] == b"%PDF-"
    from pypdf import PdfReader
    from io import BytesIO
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(pdf_bytes)).pages)
    assert "Hesaplama Metodolojisi" in text
    assert "Kaynakça" in text
    assert "Veri Kalitesi ve Belirsizlik" in text
    assert "Kullanılan Varsayımlar" in text
    assert "Veri Kaynağı Matrisi" in text
