"""Faz K.6 (Madde 8) — PET/rPET termoform tepsisi için sistem "PP Virgin
Enjeksiyon Sınıfı" gibi tamamen uyumsuz bir başlangıç hammaddesi
seçebiliyordu. İki ayrı kök neden vardı: (1) `common.py`'nin anahtar kelime
tablosunda "tepsi"/"termoform" hiç yoktu, PP-önce varsayılan listeye
düşüyordu; (2) tercih edilen hiçbir polimer bulunamazsa sistem veritabanının
İLK virgin malzemesine (polimer/uyum hiç kontrol edilmeden) sessizce
düşüyordu. Bu testler önce bu iki hatayı üretir, sonra düzeltmeyi kilitler."""
import pytest

from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest
from app.services.common import preferred_polymer_codes
from app.services.packaging_service import generate_initial_recipe


def test_tepsi_and_termoform_prefer_pet_not_default_pp_first():
    """Düzeltmeden ÖNCE: 'tepsi'/'termoform' anahtar kelime tablosunda
    yoktu, _DEFAULT_POLYMER_PREFERENCE'e (PP önce) düşüyordu."""
    assert preferred_polymer_codes("PET/rPET Gıda Tepsisi")[0] == "PET"
    assert preferred_polymer_codes("termoform ambalaj")[0] == "PET"
    assert preferred_polymer_codes("plastik tepsi")[0] == "PET"


def _material(db, polymer_code, name):
    polymer = Polymer(code=polymer_code, name=polymer_code, category="polyester", base_properties={})
    db.add(polymer)
    db.flush()
    m = Material(
        polymer_id=polymer.id, name=name, material_type="virgin", density_g_cm3=1.3,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _line(db, name="Termoform Hattı K6"):
    line = ProductionLine(
        name=name, process_type="Thermoforming", layer_structure="A", layer_count=1,
        min_micron=200.0, max_micron=900.0, supported_packaging_types=["plastik_tepsi"],
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def _request(db, packaging_type="PET/rPET Gıda Tepsisi"):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test k6", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_generate_initial_recipe_never_silently_picks_incompatible_polymer(db_session):
    """Hattaki TEK malzeme PVC -- PET/rPET tepsisi için tercih edilen
    listede (PET/PP) hiç YOK. Düzeltmeden ÖNCE: sistem tercih edilen hiçbir
    eşleşme bulamayınca veritabanının İLK virgin malzemesine (polimer hiç
    kontrol edilmeden) sessizce düşerdi -- ki o da bu PVC malzemesi olurdu.
    Düzeltmeden SONRA: açık bir ValueError fırlatılır, hiçbir reçete
    üretilmez (uyumsuz malzeme ASLA sessizce kabul edilmez)."""
    incompatible_pvc = _material(db_session, "PVC", "PVC Virgin (Tepsi İçin Uygun Değil)")
    line = _line(db_session)
    db_session.add(LineMaterialCompatibility(line_id=line.id, material_id=incompatible_pvc.id, max_ratio_pct=100.0))
    db_session.commit()

    req = _request(db_session)

    with pytest.raises(ValueError, match="uyumlu bir virgin hammadde"):
        generate_initial_recipe(db_session, req, line)


def test_generate_initial_recipe_picks_compatible_pet_when_available(db_session):
    """Aynı senaryoda hatta GERÇEKTEN uyumlu bir PET malzemesi de varsa,
    reçete PP DEĞİL PET malzemesiyle üretilmeli."""
    incompatible_pp = _material(db_session, "PP", "PP Virgin Enjeksiyon Sınıfı")
    compatible_pet = _material(db_session, "PET", "PET Virgin Şişe/Tabak Sınıfı")
    line = _line(db_session, name="Termoform Hattı K6 (PET uyumlu)")
    db_session.add(LineMaterialCompatibility(line_id=line.id, material_id=incompatible_pp.id, max_ratio_pct=100.0))
    db_session.add(LineMaterialCompatibility(line_id=line.id, material_id=compatible_pet.id, max_ratio_pct=100.0))
    db_session.commit()

    req = _request(db_session)
    recipe = generate_initial_recipe(db_session, req, line)

    assert len(recipe.layers) == 1
    assert recipe.layers[0].material_id == compatible_pet.id
