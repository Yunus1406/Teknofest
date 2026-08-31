"""Faz G.5 — Aşama 7'nin "Veri Kaynağı" etiketleri + genişletilmiş Karar
Dayanağı. `compute_data_source_tags` saf fonksiyon testleri (DB'siz) +
`run_optimization`'ın gerçekten `Recipe.data_source_tags` ve
`decision_basis`'in yeni alanlarını (hammadde_veri_foyu_sayisi,
karbon_ef_versiyonu, gecmis_recete_kademe, GERÇEKTEN dolan gecmis_receteler)
doldurduğunu doğrulayan uçtan uca testler."""
from types import SimpleNamespace

from app.knowledge_base.loader import load_all
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
from app.models.knowledge import Material
from app.models.optimization import OptimizationCandidate
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services import optimization_service
from app.services.optimization_service import compute_data_source_tags
from app.services.packaging_service import generate_initial_recipe


def _fake_candidate(material_specs: list) -> SimpleNamespace:
    return SimpleNamespace(layers=[SimpleNamespace(material=m) for m in material_specs])


def _fake_material(technical_datasheet_ref=None, carbon_ef_status="tanimli_gercek"):
    return SimpleNamespace(technical_datasheet_ref=technical_datasheet_ref, carbon_ef_status=carbon_ef_status)


# --- compute_data_source_tags: saf fonksiyon testleri -----------------------

def test_always_includes_hesaplanan():
    candidate = _fake_candidate([_fake_material()])
    tags = compute_data_source_tags(candidate, {"gecmis_receteler": [], "mevzuat_maddeleri": []})
    assert "hesaplanan" in tags


def test_gecmis_uretim_only_when_reference_evidence_present():
    candidate = _fake_candidate([_fake_material()])
    with_ref = compute_data_source_tags(candidate, {"gecmis_receteler": ["r1"], "mevzuat_maddeleri": []})
    without_ref = compute_data_source_tags(candidate, {"gecmis_receteler": [], "mevzuat_maddeleri": []})
    assert "gecmis_uretim" in with_ref
    assert "gecmis_uretim" not in without_ref


def test_teknik_veri_foyu_only_when_any_material_has_datasheet_ref():
    with_sheet = _fake_candidate([_fake_material(technical_datasheet_ref="TDS-001.pdf")])
    without_sheet = _fake_candidate([_fake_material(technical_datasheet_ref=None)])
    basis = {"gecmis_receteler": [], "mevzuat_maddeleri": []}
    assert "teknik_veri_foyu" in compute_data_source_tags(with_sheet, basis)
    assert "teknik_veri_foyu" not in compute_data_source_tags(without_sheet, basis)


def test_mevzuat_only_when_regulations_present():
    candidate = _fake_candidate([_fake_material()])
    with_reg = compute_data_source_tags(candidate, {"gecmis_receteler": [], "mevzuat_maddeleri": ["PPWR-ART-7"]})
    without_reg = compute_data_source_tags(candidate, {"gecmis_receteler": [], "mevzuat_maddeleri": []})
    assert "mevzuat" in with_reg
    assert "mevzuat" not in without_reg


def test_varsayimsal_when_any_material_carbon_undefined_or_demo():
    basis = {"gecmis_receteler": [], "mevzuat_maddeleri": []}
    for status in ("tanimlanmadi", "tanimli_demo"):
        candidate = _fake_candidate([_fake_material(carbon_ef_status=status)])
        assert "varsayimsal" in compute_data_source_tags(candidate, basis)


def test_no_varsayimsal_when_all_materials_have_real_carbon_ef():
    candidate = _fake_candidate([_fake_material(carbon_ef_status="tanimli_gercek")])
    tags = compute_data_source_tags(candidate, {"gecmis_receteler": [], "mevzuat_maddeleri": []})
    assert "varsayimsal" not in tags


def test_minimal_case_only_hesaplanan():
    """Hiçbir ek koşul tetiklenmediğinde -- SADECE 'hesaplanan' etiketi
    olmalı, uydurma başka bir kaynak ASLA eklenmez."""
    candidate = _fake_candidate([_fake_material(technical_datasheet_ref=None, carbon_ef_status="tanimli_gercek")])
    tags = compute_data_source_tags(candidate, {"gecmis_receteler": [], "mevzuat_maddeleri": []})
    assert tags == ["hesaplanan"]


def test_firma_verisi_makineden_alinan_laboratuvar_never_appear():
    """Aşama 7'nin adayları henüz üretilmedi -- bu 3 etiket burada ASLA
    eklenmemeli (ancak Aşama 10-12'de gerçek üretim/lab verisiyle anlamlı
    olurlar)."""
    candidate = _fake_candidate([_fake_material(technical_datasheet_ref="TDS.pdf", carbon_ef_status="tanimlanmadi")])
    tags = compute_data_source_tags(
        candidate, {"gecmis_receteler": ["r1"], "mevzuat_maddeleri": ["PPWR-ART-7"]}
    )
    assert "firma_verisi" not in tags
    assert "makineden_alinan" not in tags
    assert "laboratuvar" not in tags


# --- Uçtan uca: run_optimization gerçekten dolduruyor mu --------------------

def _seed_tabak_line_and_request(db, packaging_type="plastik tabak", usage_area="gıda servisi (yemek tabağı)"):
    ids = load_all(db)
    material_ids = ids["materials"]

    line = ProductionLine(
        name="Test Hat G5 - Termoform Tabak Hattı", process_type="Thermoforming",
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
        packaging_type=packaging_type, usage_area=usage_area,
        product="tek kullanımlık yemek tabağı", target_market="AB", food_contact=True,
        target_volume_units=500_000, dimensions={"length_mm": 230, "width_mm": 230, "height_mm": 20},
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req, line


def test_run_optimization_persists_new_decision_basis_fields_and_tags(db_session):
    req, line = _seed_tabak_line_and_request(db_session)

    result = optimization_service.run_optimization(db_session, req.id, line.id, ratio_step_pct=10)

    finalist_ids = result["finalist_candidate_ids"]
    assert len(finalist_ids) > 0
    candidate = db_session.get(OptimizationCandidate, finalist_ids[0])

    assert "hammadde_veri_foyu_sayisi" in candidate.decision_basis
    assert "karbon_ef_versiyonu" in candidate.decision_basis
    assert "gecmis_recete_kademe" in candidate.decision_basis
    # Bu talep için hiç Aşama 5 çalışmadı (doğrudan run_optimization
    # çağrıldı) -- gecmis_receteler boş kalmalı, uydurulmamalı.
    assert candidate.decision_basis["gecmis_receteler"] == []
    assert candidate.decision_basis["gecmis_recete_kademe"] is None

    recipe = db_session.get(Recipe, candidate.recipe_id)
    assert recipe.data_source_tags is not None
    assert "hesaplanan" in recipe.data_source_tags
    assert "mevzuat" in recipe.data_source_tags  # bu senaryoda gerçek mevzuat maddeleri eşleşiyor
    # Bu sistemde TÜM karbon EF'leri demo/varsayımsal (bkz. carbon.py) --
    # bu yüzden "varsayimsal" etiketi gerçekten beklenir.
    assert "varsayimsal" in recipe.data_source_tags


def test_run_optimization_reuses_stage5_reference_evidence(db_session):
    """Aynı ambalaj talebi için ÖNCE Aşama 5 (generate_initial_recipe)
    çalışıp gerçek bir referans bulursa, SONRA çalışan run_optimization
    bu kanıtı `decision_basis['gecmis_receteler']`'a GERÇEKTEN taşımalı --
    eskiden bu alan sabit [] idi."""
    req1, line = _seed_tabak_line_and_request(db_session, usage_area="alan A")
    material = db_session.query(Material).filter_by(material_type="virgin").first()
    verified_ref = Recipe(
        packaging_request_id=req1.id, version=1, source="sistem_uretti",
        status="dogrulandi", total_micron=600.0, is_verified=True,
    )
    db_session.add(verified_ref)
    db_session.flush()
    db_session.add(
        RecipeLayer(recipe_id=verified_ref.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=600.0)
    )
    db_session.commit()

    req2, _ = _seed_tabak_line_and_request(db_session, usage_area="alan B")  # aynı packaging_type, farklı case
    seed_recipe = generate_initial_recipe(db_session, req2, line)
    assert seed_recipe.reference_search_evidence is not None
    assert seed_recipe.reference_search_evidence["tier"] == "ayni_ambalaj_turu"

    result = optimization_service.run_optimization(db_session, req2.id, line.id, ratio_step_pct=10)

    finalist_ids = result["finalist_candidate_ids"]
    candidate = db_session.get(OptimizationCandidate, finalist_ids[0])
    assert candidate.decision_basis["gecmis_receteler"] == [verified_ref.id]
    assert candidate.decision_basis["gecmis_recete_kademe"] == "ayni_ambalaj_turu"

    recipe = db_session.get(Recipe, candidate.recipe_id)
    assert "gecmis_uretim" in recipe.data_source_tags
