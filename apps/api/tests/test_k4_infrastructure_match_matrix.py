"""Faz K.4 (Madde 6) — "uygun üretim hattı bulunamadı" derken sistem hiçbir
gerekçe vermiyordu; uyumsuz hatlar `match_infrastructure`'dan SESSİZCE
düşürülüyordu (hiçbir kayıt/gerekçe tutulmadan). Bu testler önce bu hatayı
üretir (uyumsuz bir hat sonuçta HİÇ görünmüyordu), sonra düzeltmeyi -- her
hattın kriter matrisi + skoru + eksik gerekçesiyle sonuçta kalmasını --
kilitler."""
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest
from app.services.packaging_service import match_infrastructure


def _polymer(db, code="PP"):
    # "tepsi" _PACKAGING_KEYWORD_RULES'da (henüz K.6 öncesi) tanımlı DEĞİL,
    # bu yüzden preferred_polymer_codes() varsayılan listeye ["PP","PE","PET"]
    # düşer -- burada bilerek tam o listedeki bir kod kullanılıyor.
    p = Polymer(code=code, name=f"Polimer {code}", category="polyester", base_properties={})
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _material(db, polymer, food_contact_eligible=True):
    m = Material(
        polymer_id=polymer.id, name=f"{polymer.code} Virgin K4", material_type="virgin", density_g_cm3=1.3,
        degradation_factor=0.0, food_contact_eligible=food_contact_eligible, max_recommended_ratio_pct=100.0,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _line(db, name, supported_packaging_types, min_micron=20.0, max_micron=500.0, process_type="Termoform"):
    line = ProductionLine(
        name=name, process_type=process_type, layer_structure="A", layer_count=1,
        min_micron=min_micron, max_micron=max_micron, supported_packaging_types=supported_packaging_types,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def _request(db, packaging_type="plastik tepsi k4", target_thickness_micron=None):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test k4", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
        target_thickness_micron=target_thickness_micron,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_fully_compatible_line_is_eligible_with_full_criteria(db_session):
    polymer = _polymer(db_session)
    material = _material(db_session, polymer)
    line = _line(db_session, "Uygun Hat K4", supported_packaging_types=["plastik tepsi k4"])
    db_session.add(LineMaterialCompatibility(line_id=line.id, material_id=material.id, max_ratio_pct=100.0))
    db_session.commit()

    req = _request(db_session, target_thickness_micron=100.0)
    results = match_infrastructure(db_session, req)

    mine = next(r for r in results if r["line"].id == line.id)
    assert mine["eligible"] is True
    assert mine["score_pct"] == 100
    assert mine["criteria"] == {
        "proses": True, "malzeme_uyumu": True, "mikron_araligi": True,
        "katman_yapisi": True, "ambalaj_turu": True,
    }
    assert mine["missing"] == []


def test_incompatible_packaging_type_line_still_appears_with_reason(db_session):
    """Düzeltmeden ÖNCE: bu hat sonuçta HİÇ görünmezdi (sessizce elenirdi).
    Düzeltmeden SONRA: hat sonuçta kalır, eligible=False, gerekçesi net."""
    polymer = _polymer(db_session, code="PP")
    material = _material(db_session, polymer)
    line = _line(db_session, "Uyumsuz Tür Hattı K4", supported_packaging_types=["plastik şişe"])
    db_session.add(LineMaterialCompatibility(line_id=line.id, material_id=material.id, max_ratio_pct=100.0))
    db_session.commit()

    req = _request(db_session, packaging_type="plastik tepsi k4 farklı")
    results = match_infrastructure(db_session, req)

    mine = next((r for r in results if r["line"].id == line.id), None)
    assert mine is not None, "Uyumsuz hat SESSİZCE sonuçtan düşürülmemeli -- gerekçesiyle görünmeli"
    assert mine["eligible"] is False
    assert mine["criteria"]["ambalaj_turu"] is False
    assert any("ambalaj türü" in m for m in mine["missing"])


def test_thickness_outside_range_marked_ineligible_with_reason(db_session):
    polymer = _polymer(db_session, code="PP")
    material = _material(db_session, polymer)
    line = _line(db_session, "Dar Aralık Hattı K4", supported_packaging_types=["plastik tepsi k4 dar"], min_micron=10.0, max_micron=50.0)
    db_session.add(LineMaterialCompatibility(line_id=line.id, material_id=material.id, max_ratio_pct=100.0))
    db_session.commit()

    req = _request(db_session, packaging_type="plastik tepsi k4 dar", target_thickness_micron=450.0)
    results = match_infrastructure(db_session, req)

    mine = next(r for r in results if r["line"].id == line.id)
    assert mine["eligible"] is False
    assert mine["criteria"]["mikron_araligi"] is False
    assert any("µm" in m for m in mine["missing"])


def test_eligible_lines_sort_before_ineligible_regardless_of_raw_score(db_session):
    """seed_demo.py ve Aşama 4'ün 'ilk eşleşeni öner' mantığı `matches[0]`'ı
    kullanır -- bu yüzden eligible bir hat HER ZAMAN ineligible bir hattan
    önce gelmeli, ham skor eşit/yakın olsa bile."""
    polymer = _polymer(db_session, code="PP")
    good_material = _material(db_session, polymer)
    good_line = _line(db_session, "Skor Testi Uygun Hat", supported_packaging_types=["plastik tepsi k4 skor"])
    db_session.add(LineMaterialCompatibility(line_id=good_line.id, material_id=good_material.id, max_ratio_pct=100.0))

    # Bu hat proses+katman ile aynı ham skora (80%) yaklaşabilir ama ambalaj
    # türü desteklemediği için eligible=False olmalı.
    bad_line = _line(db_session, "Skor Testi Uyumsuz Hat", supported_packaging_types=["bambaşka tür"])
    db_session.add(LineMaterialCompatibility(line_id=bad_line.id, material_id=good_material.id, max_ratio_pct=100.0))
    db_session.commit()

    req = _request(db_session, packaging_type="plastik tepsi k4 skor")
    results = match_infrastructure(db_session, req)

    assert results[0]["line"].id == good_line.id
    assert results[0]["eligible"] is True


def test_status_only_matched_when_at_least_one_eligible_line(db_session):
    line = _line(db_session, "Hiç Uygun Olmayan Hat K4", supported_packaging_types=["tamamen alakasız tür"])
    db_session.commit()

    req = _request(db_session, packaging_type="eşleşmeyecek tür k4")
    results = match_infrastructure(db_session, req)

    assert all(not r["eligible"] for r in results)
    assert req.status != "eslesme_tamam"
