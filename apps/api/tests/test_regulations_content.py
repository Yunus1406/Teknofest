"""Mevzuat içeriği/madde numaraları ve Aşama 3 değerlendirme metinleri için
regresyon testleri. Bilgi tabanı (YAML) + değerlendirme mantığı birlikte
test edilir — DB fixture kullanılır."""
from app.knowledge_base.loader import load_all
from app.models.knowledge import Regulation
from app.models.recipe import PackagingRequest
from app.services.packaging_service import assess_regulations


def _request(db, food_contact=True, packaging_type="plastik tabak"):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test", target_market="AB",
        food_contact=food_contact, target_volume_units=1000, dimensions={"length_mm": 200, "width_mm": 200},
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_minimization_regulation_is_article_10_not_3(db_session):
    load_all(db_session)
    reg = db_session.query(Regulation).filter_by(code="PPWR-ART-10").one_or_none()
    assert reg is not None, "PPWR-ART-10 bilgi tabanında bulunamadı"
    assert "Md.10" in reg.title or "Madde 10" in reg.title
    assert db_session.query(Regulation).filter_by(code="PPWR-ART-3").one_or_none() is None


def test_assessment_reasoning_cites_article_10_for_minimization(db_session):
    load_all(db_session)
    req = _request(db_session)

    overall, assessments = assess_regulations(db_session, req)

    minimization = next(
        a for a in assessments
        if db_session.get(Regulation, a.regulation_id).code == "PPWR-ART-10"
    )
    assert "Md.10" in minimization.reasoning
    assert "Md.3" not in minimization.reasoning


# --- Fix #6: Md.7 sabit %30 yerine kategori+tarih tablosu ------------------

def test_pcr_content_uses_category_table_not_hardcoded_30_percent(db_session):
    load_all(db_session)
    # "plastik tabak" -> preferred_polymer_codes ilk tercih PP (PET değil).
    req = _request(db_session, food_contact=True, packaging_type="plastik tabak")

    overall, assessments = assess_regulations(db_session, req)

    pcr = next(
        a for a in assessments
        if db_session.get(Regulation, a.regulation_id).code == "PPWR-ART-7"
    )
    assert "%10" in pcr.reasoning
    assert "%25" in pcr.reasoning
    assert "%30" not in pcr.reasoning
    assert "Regranül/PIR: Md.7 hesabına dahil değil" in pcr.reasoning
    assert "Kategori:" in pcr.reasoning


# --- Fix #7: PFAS (PPWR Md.5) yalnızca gıda temaslı ambalajlarda ----------

def test_pfas_card_present_when_food_contact(db_session):
    load_all(db_session)
    req = _request(db_session, food_contact=True)

    overall, assessments = assess_regulations(db_session, req)

    pfas = next(
        (a for a in assessments if db_session.get(Regulation, a.regulation_id).code == "PPWR-ART-5"),
        None,
    )
    assert pfas is not None
    assert "PFAS" in pfas.reasoning
    # Faz G.2 — gerçek PFAS ppb/ppm ölçümü otomatikleştirilemez, laboratuvar
    # testi gerekir -- bu artık "kullanıcı karar versin" (REVIEW) değil,
    # "henüz uygulanabilir metodoloji yok" (NO_METHODOLOGY).
    assert "Henüz Uygulanabilir Metodoloji Bulunmuyor" in pfas.reasoning
    assert pfas.verdict == "henuz_metodoloji_yok"


def test_pfas_card_absent_when_not_food_contact(db_session):
    load_all(db_session)
    req = _request(db_session, food_contact=False)

    overall, assessments = assess_regulations(db_session, req)

    pfas = next(
        (a for a in assessments if db_session.get(Regulation, a.regulation_id).code == "PPWR-ART-5"),
        None,
    )
    assert pfas is None


# --- Fix #8: FCM iki seviyeli değerlendirme, tek başına 'Uygun' değil -----

def test_fcm_never_returns_plain_ok_for_food_contact_packaging(db_session):
    load_all(db_session)
    req = _request(db_session, food_contact=True)

    overall, assessments = assess_regulations(db_session, req)

    fcm = next(
        a for a in assessments
        if db_session.get(Regulation, a.regulation_id).code == "EU-FCM-1935-2004"
    )
    # Faz G.2 — nihai ambalajın migrasyon testinden geçtiğini doğrulamak
    # yapısal olarak otomatikleştirilemez; bu artık "kullanıcı karar versin"
    # (REVIEW) değil, "henüz uygulanabilir metodoloji yok" (NO_METHODOLOGY) --
    # ama test adının garantisi (asla düz bir "Uygun" dönmez) hâlâ geçerli.
    assert fcm.verdict == "henuz_metodoloji_yok"
    assert "Hammadde Belgesi" in fcm.reasoning
    assert "Nihai Ambalaj Uygunluğu: Doğrulama Gerekli" in fcm.reasoning
