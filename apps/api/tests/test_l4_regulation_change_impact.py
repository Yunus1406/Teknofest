"""Faz L.4 (Madde 17) — bir mevzuat kaydı güncellendiğinde sistem hangi
ürünleri/SKU'ları etkilediğini bulmalı; bu analiz Nihai Rapor'a ("Kullanılan
Mevzuat Sürümü ve Değişiklik Geçmişi") ve Dijital Ürün Pasaportu'na
(kimlik kartı alanları) yansımalı."""
import pytest

from app.knowledge_base.loader import load_all
from app.models.knowledge import Material, Polymer
from app.models.product_sku import ProductSku
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.models.regulation_requirement import RegulationRequirement
from app.services import pdf_service
from app.services.packaging_service import assess_regulations
from app.services.passport_service import build_passport_content, get_or_create_passport
from app.services.regulation_impact_service import analyze_regulation_change_impact
from app.services.report_service import build_optimization_report_data


def _material(db):
    polymer = db.query(Polymer).filter_by(code="PP").one_or_none()
    if polymer is None:
        polymer = Polymer(code="PP", name="Polipropilen", category="poliolefin", base_properties={})
        db.add(polymer)
        db.flush()
    m = Material(
        polymer_id=polymer.id, name="PP Virgin L4", material_type="virgin", density_g_cm3=0.905,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=38.0, carbon_factor_kg_co2_per_kg=1.9,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _sku_with_assessed_request(db, material, sku_code="SKU-L4-001"):
    sku = ProductSku(
        sku_code=sku_code, product_name="Test Ürün L4", packaging_type="plastik tabak",
        usage_area="test l4", target_market="AB", food_contact=True,
    )
    db.add(sku)
    db.flush()

    req = PackagingRequest(
        packaging_type="plastik tabak", usage_area="test l4", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 200, "width_mm": 200},
        sku_id=sku.id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    overall, assessments = assess_regulations(db, req)
    return sku, req, assessments


def _verified_recipe_for(db, req, material, thickness=70.0):
    recipe = Recipe(
        packaging_request_id=req.id, version=1, source="sistem_uretti", status="dogrulandi",
        is_verified=True, total_micron=thickness,
    )
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=thickness))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_unknown_regulation_code_raises(db_session):
    load_all(db_session)
    with pytest.raises(ValueError):
        analyze_regulation_change_impact(db_session, "BILINMEYEN-KOD")


def test_no_active_skus_returns_zero_counts(db_session):
    load_all(db_session)
    result = analyze_regulation_change_impact(db_session, "PPWR-ART-7")
    assert result["total_active_skus"] == 0
    assert result["affected_sku_count"] == 0


def test_sku_becomes_affected_after_version_bump(db_session):
    ids = load_all(db_session)
    material = _material(db_session)
    sku, req, assessments = _sku_with_assessed_request(db_session, material)

    art7 = next(a for a in assessments if a.regulation.code == "PPWR-ART-7")
    assert art7.regulation_version_snapshot == "1.0"

    # GMP 2023/2006: generic yoldan default_verdict="henuz_metodoloji_yok"
    # döner -- KB'deki hammadde kompozisyonundan BAĞIMSIZ, güvenilir bir
    # "OK değil" senaryosu (PPWR-ART-7'nin verdict'i KB'deki demo PCR
    # malzemelerin varlığına göre değişebiliyor, bu test o belirsizliğe
    # duyarlı olmasın diye GMP kullanılıyor).
    before = analyze_regulation_change_impact(db_session, "EU-GMP-2023-2006")
    assert before["total_active_skus"] == 1
    assert before["affected_sku_count"] == 0

    # Mevzuat güncellenir (canlı RegulationRequirement satırları yeni bir
    # sürüme çekilir) -- artık bu SKU'nun snapshot'ı GÜNCEL değil.
    rows = db_session.query(RegulationRequirement).filter_by(regulation_id=ids["regulations"]["EU-GMP-2023-2006"]).all()
    for row in rows:
        row.version = "2.0"
    db_session.commit()

    after = analyze_regulation_change_impact(db_session, "EU-GMP-2023-2006")
    assert after["current_version"] == "2.0"
    assert after["affected_sku_count"] == 1
    assert sku.sku_code in after["affected_sku_codes"]
    # GMP verdict'i her zaman henuz_metodoloji_yok (OK değil).
    assert after["evidence_needed_count"] == 1
    # Henüz doğrulanmış bir reçetesi yok -- reçete yeniden değerlendirme sayılmaz.
    assert after["recipe_reassessment_count"] == 0


def test_recipe_reassessment_count_when_sku_has_verified_recipe(db_session):
    ids = load_all(db_session)
    material = _material(db_session)
    sku, req, assessments = _sku_with_assessed_request(db_session, material, sku_code="SKU-L4-002")
    recipe = _verified_recipe_for(db_session, req, material)
    sku.current_recipe_id = recipe.id
    db_session.commit()

    rows = db_session.query(RegulationRequirement).filter_by(regulation_id=ids["regulations"]["PPWR-ART-7"]).all()
    for row in rows:
        row.version = "3.0"
    db_session.commit()

    result = analyze_regulation_change_impact(db_session, "PPWR-ART-7")
    assert result["recipe_reassessment_count"] == 1


def test_report_includes_regulation_version_history_with_real_snapshot(db_session):
    load_all(db_session)
    material = _material(db_session)
    sku, req, assessments = _sku_with_assessed_request(db_session, material, sku_code="SKU-L4-003")
    recipe = _verified_recipe_for(db_session, req, material)

    data = build_optimization_report_data(db_session, recipe.id)

    assert "mevzuat_versiyon_gecmisi" in data
    items = data["mevzuat_versiyon_gecmisi"]["items"]
    assert len(items) > 0
    art7_item = next(i for i in items if i["regulation_code"] == "PPWR-ART-7")
    assert art7_item["used_version"] == "1.0"
    assert art7_item["current_version"] == "1.0"
    assert art7_item["changed_since_assessment"] is False

    # PDF hatasız üretilmeli (yeni 22. bölüm dahil).
    pdf_bytes = pdf_service.render_technical_report(data)
    assert pdf_bytes[:5] == b"%PDF-"


def test_passport_header_has_regulatory_fields(db_session):
    load_all(db_session)
    material = _material(db_session)
    sku, req, assessments = _sku_with_assessed_request(db_session, material, sku_code="SKU-L4-004")
    recipe = _verified_recipe_for(db_session, req, material)

    passport = get_or_create_passport(db_session, recipe.id)
    content = build_passport_content(db_session, passport, include_authorized=False)

    header = content["public"]["header"]
    assert header["regulatory_assessment_date"] is not None
    assert "1.0" in header["regulation_versions_used"]
    assert header["last_checked_date"] == header["regulatory_assessment_date"]
    assert header["affected_by_recent_change"] is False
