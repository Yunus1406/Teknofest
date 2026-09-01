"""Faz L.2 (Madde 4) — gıda temaslı plastik ambalajlar için otomatik kanıt
yönetim listesi: 1935/2004, (EU) 10/2011, GMP 2023/2006, (EU) 2022/1616
(rPET/PCR gıda temaslıysa EK OLARAK), DoC, migrasyon, hammadde uygunluk
belgeleri, PCR/rPET kaynak-proses kanıtları, kimyasal/test kanıtları. Her
kanıt Mevcut ✓ / Eksik ⚠ / Gerekli Değil durumuyla."""
from app.knowledge_base.loader import load_all
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest
from app.services.packaging_service import assess_regulations, build_food_contact_evidence_checklist


def _request(db, food_contact=True, packaging_type="plastik tabak"):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test l2", product="test", target_market="AB",
        food_contact=food_contact, target_volume_units=1000, dimensions={"length_mm": 200, "width_mm": 200},
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_checklist_empty_when_not_food_contact(db_session):
    req = _request(db_session, food_contact=False)
    assert build_food_contact_evidence_checklist(db_session, req) == []


def test_checklist_has_all_9_items_when_food_contact(db_session):
    req = _request(db_session, food_contact=True)
    checklist = build_food_contact_evidence_checklist(db_session, req)

    types = {item["evidence_type"] for item in checklist}
    assert len(checklist) == 9
    assert "1935/2004 Çerçeve Uygunluğu (DoC)" in types
    assert "(EU) 10/2011 Migrasyon Limitleri" in types
    assert "GMP 2023/2006 İyi Üretim Uygulamaları" in types
    assert "(EU) 2022/1616 Geri Dönüştürülmüş Plastik Çerçevesi" in types
    assert all(item["status"] in ("mevcut", "eksik", "gerekli_degil") for item in checklist)


def test_2022_1616_gerekli_degil_when_no_food_grade_pcr_in_kb(db_session):
    req = _request(db_session, food_contact=True)
    checklist = build_food_contact_evidence_checklist(db_session, req)
    item = next(i for i in checklist if "2022/1616" in i["evidence_type"])
    assert item["status"] == "gerekli_degil"


def test_2022_1616_becomes_eksik_when_food_grade_pcr_exists(db_session):
    polymer = Polymer(code="PETL2", name="Polyester L2", category="polyester", base_properties={})
    db_session.add(polymer)
    db_session.flush()
    db_session.add(
        Material(
            polymer_id=polymer.id, name="rPET Gıda Sınıfı L2", material_type="pcr", density_g_cm3=1.3,
            degradation_factor=0.05, food_contact_eligible=True, max_recommended_ratio_pct=50.0,
        )
    )
    db_session.commit()

    req = _request(db_session, food_contact=True)
    checklist = build_food_contact_evidence_checklist(db_session, req)
    item = next(i for i in checklist if "2022/1616" in i["evidence_type"])
    assert item["status"] == "eksik"


def test_hammadde_belgeleri_mevcut_when_certification_status_filled(db_session):
    polymer = Polymer(code="PEL2", name="Polietilen L2", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()
    db_session.add(
        Material(
            polymer_id=polymer.id, name="PE Virgin Sertifikalı L2", material_type="virgin", density_g_cm3=0.92,
            degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
            certification_status="ISO 22000 sertifikalı",
        )
    )
    db_session.commit()

    req = _request(db_session, food_contact=True)
    checklist = build_food_contact_evidence_checklist(db_session, req)
    item = next(i for i in checklist if i["evidence_type"] == "Hammadde Uygunluk Belgeleri")
    assert item["status"] == "mevcut"


def test_evidence_checklist_included_in_assess_regulations_endpoint_flow(db_session):
    """assess_regulations() ayrı bir fonksiyon olsa da, router'ın gerçekten
    her ikisini de (assessments + evidence_checklist) tek yanıtta birleştirip
    birleştirmediğini router seviyesinde test etmiyoruz burada (o HTTP testi
    başka dosyada) -- burada sadece iki fonksiyonun AYNI request için tutarlı
    çalıştığını doğruluyoruz (assess_regulations reçeteyi bozmuyor)."""
    load_all(db_session)
    req = _request(db_session, food_contact=True)

    overall, assessments = assess_regulations(db_session, req)
    checklist = build_food_contact_evidence_checklist(db_session, req)

    assert len(assessments) > 0
    assert len(checklist) == 9
    # GMP artık gıda temaslı taleplerde aktif değerlendirmelerin arasında.
    gmp_codes = {a.regulation.code for a in assessments}
    assert "EU-GMP-2023-2006" in gmp_codes
