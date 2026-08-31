"""Faz B.8 — PPWR Kural Kütüphanesi (tablo-güdümlü). `test_regulations_
content.py`'nin tüm Faz A regresyon testleri (madde numaraları, PCR
yüzdeleri, PFAS, FCM iki seviyeli değerlendirme) bu refactor sonrası da
aynı davranışı üretmeli — bu dosya EK olarak tablo-okuma mekanizmasının
kendisini doğrular: (a) yükleyicinin doğru satır sayısını/kategori-yıl
kırılımını yazdığını, (b) yeni bir madde eklemenin GERÇEKTEN sadece yeni
bir DB satırı gerektirdiğini (yeni bir if/elif dalı DEĞİL)."""
from app.knowledge_base.loader import load_all
from app.models.enums import RegulatoryVerdict
from app.models.knowledge import Regulation
from app.models.recipe import PackagingRequest
from app.models.regulation_requirement import RegulationRequirement
from app.services.packaging_service import _assess_single_regulation, assess_regulations


def _request(db, food_contact=True, packaging_type="plastik tabak"):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test", target_market="AB",
        food_contact=food_contact, target_volume_units=1000, dimensions={"length_mm": 200, "width_mm": 200},
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_ppwr_art7_loads_two_year_rows_for_reference_category(db_session):
    ids = load_all(db_session)
    reg_id = ids["regulations"]["PPWR-ART-7"]

    rows = (
        db_session.query(RegulationRequirement)
        .filter_by(regulation_id=reg_id, packaging_category="gida_temasli_pet_disi_plastik")
        .order_by(RegulationRequirement.target_year)
        .all()
    )

    assert [r.target_year for r in rows] == [2030, 2040]
    assert "%10" in rows[0].requirement_text
    assert "%25" in rows[1].requirement_text
    assert all(r.pcr_only for r in rows)


def test_minimization_article_comes_from_db_row_not_hardcoded_string(db_session):
    """PPWR-ART-10'un madde numarası artık `RegulationRequirement.article`
    satırından geliyor — DB'deki değeri değiştirirsek reasoning de değişmeli
    (kod içinde SABİT bir 'Md.10' string'i kalmadığının kanıtı)."""
    load_all(db_session)
    reg = db_session.query(Regulation).filter_by(code="PPWR-ART-10").one()
    requirement = db_session.query(RegulationRequirement).filter_by(regulation_id=reg.id).one()
    requirement.article = "Md.99-TEST"
    db_session.commit()

    req = _request(db_session)
    verdict, reasoning = _assess_single_regulation(db_session, reg, req, food_grade_pcr_exists=False)

    assert "Md.99-TEST" in reasoning


def test_new_regulation_requirement_row_needs_no_code_change(db_session):
    """B.8'in temel iddiası: basit (tek satırlık) bir madde eklemek yeni bir
    if/elif dalı DEĞİL, sadece yeni bir `RegulationRequirement` satırı
    gerektirir. Burada bilgi tabanında hiç yer almayan uydurma bir madde
    kodu için satır ekleyip, genel (fallback) yolun onu doğrudan DB'den
    okuyup verdiğini doğruluyoruz."""
    load_all(db_session)
    fake_reg = Regulation(
        code="TEST-REG-999",
        title="Test Maddesi",
        category="test",
        description="Test",
        criteria={},
        applicable_packaging_types=[],
    )
    db_session.add(fake_reg)
    db_session.flush()
    db_session.add(
        RegulationRequirement(
            regulation_id=fake_reg.id,
            regulation_no="TEST-REG",
            article="Md.999",
            requirement_text="Bu tamamen test amaçlı bir gerekliliktir.",
            default_verdict=RegulatoryVerdict.OK.value,
        )
    )
    db_session.commit()

    req = _request(db_session)
    verdict, reasoning = _assess_single_regulation(db_session, fake_reg, req, food_grade_pcr_exists=False)

    assert verdict == RegulatoryVerdict.OK.value
    assert reasoning == "Bu tamamen test amaçlı bir gerekliliktir."


def test_assess_regulations_end_to_end_still_produces_overall_verdict(db_session):
    """Tam entegrasyon: assess_regulations() (Aşama 3 orkestrasyonu) refactor
    sonrası da genel bir sonuç üretmeye devam ediyor."""
    load_all(db_session)
    req = _request(db_session)
    overall, assessments = assess_regulations(db_session, req)
    assert overall in {v.value for v in RegulatoryVerdict}
    assert len(assessments) > 0
