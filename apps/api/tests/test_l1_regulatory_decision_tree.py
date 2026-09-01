"""Faz L.1 (Madde 3) — Mevzuat motoru gerçek bir karar ağacı kullanmalı:
Hedef Pazar → Ambalaj Malzemesi → Kullanım → Gıda Teması → Ambalaj
Kategorisi → İstisnalar → Uygulanacak Madde → Hedef Tarih; her adım
`RegulatoryAssessment.decision_trail`'de yapılandırılmış olarak izlenebilir
olmalı ("Bu kural neden uygulanıyor?").

Bildirilen spesifik hata (PET/rPET gıda tepsisi için PET-dışı PPWR Md.7
oranlarının yanlışlıkla uygulanması) Faz K.6'nın "tepsi"/"termoform"
anahtar kelime eklemesiyle ZATEN düzeltildi -- bu dosyadaki
`test_pet_tray_never_gets_pet_disi_numbers` o düzeltmeyi bu katmanda da
kilitler (regresyon kilidi, yeniden üretim değil)."""
from app.knowledge_base.loader import load_all
from app.models.recipe import PackagingRequest
from app.services.packaging_service import _target_market_eu_status, assess_regulations


def _request(db, packaging_type="plastik tabak", target_market="AB", food_contact=True):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test l1", product="test", target_market=target_market,
        food_contact=food_contact, target_volume_units=1000, dimensions={"length_mm": 200, "width_mm": 200},
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_decision_trail_populated_for_every_assessment(db_session):
    load_all(db_session)
    req = _request(db_session)

    overall, assessments = assess_regulations(db_session, req)

    assert len(assessments) > 0
    for a in assessments:
        assert a.decision_trail is not None
        for key in (
            "hedef_pazar", "hedef_pazar_ab_mi", "ambalaj_malzemesi_tahmini",
            "kullanim_alani", "gida_temasi", "ambalaj_kategorisi",
            "istisna", "uygulanan_madde", "hedef_tarih",
        ):
            assert key in a.decision_trail
        assert a.decision_trail["hedef_pazar"] == "AB"
        assert a.decision_trail["hedef_pazar_ab_mi"] == "evet"
        assert a.decision_trail["gida_temasi"] is True


def test_pet_tray_never_gets_pet_disi_numbers(db_session):
    """Regresyon kilidi (K.6): PET/rPET tepsi için PPWR Md.7'nin PET-DIŞI
    (%10/%25) hedefleri UYGULANMAMALI -- KB'de PET kategorisi için gerçek
    veri olmadığından dürüstçe 'veri_eksik' dönmeli, uydurma bir sayı
    kesinlikle görünmemeli."""
    load_all(db_session)
    req = _request(db_session, packaging_type="PET/rPET Gıda Tepsisi")

    overall, assessments = assess_regulations(db_session, req)

    pcr_assessment = next(
        a for a in assessments if a.decision_trail and "Geri Dönüştürülmüş" in a.reasoning
    )
    assert "%10" not in pcr_assessment.reasoning
    assert "%25" not in pcr_assessment.reasoning
    assert "pet dışı" not in pcr_assessment.reasoning.lower()
    # Tahmin doğru yönde: tercih sırası PET önce.
    assert pcr_assessment.decision_trail["ambalaj_malzemesi_tahmini"].startswith(
        "'PET/rPET Gıda Tepsisi' ifadesinden tahmini tercih sırası: PET/"
    )


def test_target_market_eu_status_detection():
    assert _target_market_eu_status("AB") == "evet"
    assert _target_market_eu_status("Avrupa Birliği") == "evet"
    assert _target_market_eu_status("Türkiye") == "hayir"
    assert _target_market_eu_status("ABD") == "hayir"
    assert _target_market_eu_status("Amerika") == "hayir"
    assert _target_market_eu_status(None) == "belirsiz"
    assert _target_market_eu_status("") == "belirsiz"
    assert _target_market_eu_status("Bilinmeyen Pazar XYZ") == "belirsiz"


def test_non_eu_market_adds_note_but_never_changes_verdict_or_count(db_session):
    load_all(db_session)
    req_eu = _request(db_session, target_market="AB")
    overall_eu, assessments_eu = assess_regulations(db_session, req_eu)

    req_non_eu = _request(db_session, target_market="Türkiye")
    overall_non_eu, assessments_non_eu = assess_regulations(db_session, req_non_eu)

    assert len(assessments_eu) == len(assessments_non_eu)
    assert sorted(a.verdict for a in assessments_eu) == sorted(a.verdict for a in assessments_non_eu)
    assert overall_eu == overall_non_eu

    for a in assessments_non_eu:
        assert a.decision_trail["hedef_pazar_ab_mi"] == "hayir"
        assert "doğrudan yürürlükte olmayabilir" in a.reasoning
    for a in assessments_eu:
        assert "doğrudan yürürlükte olmayabilir" not in a.reasoning
