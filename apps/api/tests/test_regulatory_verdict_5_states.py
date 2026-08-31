"""Faz G.2 — Aşama 3'ün 5 durumlu sonuç modeli: eskiden hepsi "inceleme_
gerekli"ye düşen "veri eksik" ve "otomatik doğrulanamaz" durumları artık
ayrışıyor. `_overall_verdict`'in yeni önceliği ve `regulatory_alerts`
sayacının yeni durumları alarm saymadığı da burada doğrulanır."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.knowledge_base.loader import load_all
from app.main import app
from app.models.knowledge import Regulation
from app.models.recipe import PackagingRequest, RegulatoryAssessment
from app.services.packaging_service import _overall_verdict, assess_regulations
from app.services.pdf_service import _verdict_label


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _request(db, food_contact=True, packaging_type="plastik tabak", dimensions=None):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test", target_market="AB",
        food_contact=food_contact, target_volume_units=1000,
        dimensions=dimensions if dimensions is not None else {"length_mm": 200, "width_mm": 200},
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


# --- _overall_verdict önceliği ---------------------------------------------

def test_overall_verdict_priority_order():
    assert _overall_verdict(["uygun_gorunuyor", "uygun_degil", "veri_eksik"]) == "uygun_degil"
    assert _overall_verdict(["uygun_gorunuyor", "inceleme_gerekli", "veri_eksik"]) == "inceleme_gerekli"
    assert _overall_verdict(["uygun_gorunuyor", "veri_eksik", "henuz_metodoloji_yok"]) == "veri_eksik"
    assert _overall_verdict(["uygun_gorunuyor", "henuz_metodoloji_yok"]) == "henuz_metodoloji_yok"
    assert _overall_verdict(["uygun_gorunuyor"]) == "uygun_gorunuyor"
    assert _overall_verdict([]) == "uygun_gorunuyor"


# --- Yeni MISSING_DATA dalları ----------------------------------------------

def test_minimization_missing_dimensions_is_missing_data_not_review(db_session):
    load_all(db_session)
    req = _request(db_session, dimensions={})

    overall, assessments = assess_regulations(db_session, req)

    minimization = next(
        a for a in assessments if db_session.get(Regulation, a.regulation_id).code == "PPWR-ART-10"
    )
    assert minimization.verdict == "veri_eksik"


def test_pcr_content_unmatched_category_is_missing_data(db_session):
    load_all(db_session)
    # food_contact=False + "plastik tabak" (PP tahmini) -> gida_temasli_degil_pet_disi_plastik
    # kategorisi, bilgi tabanında hiç satırı yok.
    req = _request(db_session, food_contact=False, packaging_type="plastik tabak")

    overall, assessments = assess_regulations(db_session, req)

    pcr = next(a for a in assessments if db_session.get(Regulation, a.regulation_id).code == "PPWR-ART-7")
    assert pcr.verdict == "veri_eksik"


def test_regulation_without_any_requirement_row_is_missing_data(db_session):
    """assess_regulations, RegulationRequirement satırı olmayan bir Regulation
    ile karşılaşırsa artık MISSING_DATA döner (eskiden REVIEW + 'kural
    tanımlı değil' metniydi)."""
    load_all(db_session)
    reg = Regulation(
        code="TEST-NO-REQ", title="Test Kuralı", category="test",
        description="Test", criteria={}, applicable_packaging_types=["plastik_tabak"],
    )
    db_session.add(reg)
    db_session.commit()

    req = _request(db_session, packaging_type="plastik tabak")
    overall, assessments = assess_regulations(db_session, req)

    test_reg_assessment = next(
        a for a in assessments if db_session.get(Regulation, a.regulation_id).code == "TEST-NO-REQ"
    )
    assert test_reg_assessment.verdict == "veri_eksik"


# --- Dashboard 1'in regulatory_alerts sayacı --------------------------------

def test_regulatory_alerts_excludes_missing_data_and_no_methodology(client, db_session):
    load_all(db_session)
    req = _request(db_session, food_contact=True, packaging_type="plastik tabak")
    assess_regulations(db_session, req)

    all_assessments = db_session.query(RegulatoryAssessment).all()
    verdicts_present = {a.verdict for a in all_assessments}
    # Bu senaryoda hem veri_eksik hem henuz_metodoloji_yok hem inceleme_gerekli
    # üretilmeli (PFAS->henuz_metodoloji_yok, FCM->henuz_metodoloji_yok,
    # Md.6/Md.9/Md.10 generic->inceleme_gerekli/uygun_gorunuyor).
    assert "henuz_metodoloji_yok" in verdicts_present

    resp = client.get("/api/v1/dashboard1/summary")
    assert resp.status_code == 200
    body = resp.json()

    expected_alerts = sum(1 for a in all_assessments if a.verdict in ("uygun_degil", "inceleme_gerekli"))
    assert body["regulatory_alerts"] == expected_alerts
    # henuz_metodoloji_yok/veri_eksik sayıları alarm sayısına dahil DEĞİL.
    assert body["regulatory_alerts"] < len(all_assessments)


# --- Şema genişlemesi: sub_article / last_reviewed_at / effective_date -----

def test_reference_regulation_requirements_endpoint_exposes_new_fields(client, db_session):
    load_all(db_session)
    resp = client.get("/api/v1/reference/regulation-requirements")
    assert resp.status_code == 200
    body = resp.json()

    art10 = next(r for r in body if r["article"] == "Md.10")
    assert art10["sub_article"] == "Ek IV"
    assert art10["last_reviewed_at"] is not None

    art5 = next(r for r in body if r["article"] == "Md.5")
    assert art5["sub_article"] == "Fıkra 5"
    assert art5["effective_date"] is not None

    art6 = next(r for r in body if r["article"] == "Md.6")
    assert art6["sub_article"] is None  # bilinmeyen alan uydurulmadı, dürüstçe null


# --- PDF servisi yeni durumları çökmeden render ediyor ----------------------

def test_pdf_verdict_label_covers_new_states():
    assert _verdict_label("veri_eksik") == "Veri Eksik"
    assert _verdict_label("henuz_metodoloji_yok") == "Henüz Uygulanabilir Metodoloji Bulunmuyor"
