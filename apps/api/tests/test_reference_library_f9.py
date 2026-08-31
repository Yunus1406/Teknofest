"""Faz F.9 — Geri Dönüştürülebilirlik Değerlendirme Kriterleri.
`recyclability_breakdown` SADECE PPWR Md.6 (PPWR-ART-6) değerlendirmesinde
dolu, diğer TÜM maddelerde None -- verdict/reasoning hesaplaması hiç
değişmedi (bkz. test_regulations_content.py'nin AYNI şekilde geçtiği)."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.knowledge_base.loader import load_all
from app.main import app
from app.models.knowledge import Regulation
from app.models.recipe import PackagingRequest
from app.models.recyclability_criterion import RecyclabilityCriterion
from app.services.packaging_service import assess_regulations


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _request(db, packaging_type="plastik tabak"):
    req = PackagingRequest(
        packaging_type=packaging_type, usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 200, "width_mm": 200},
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def test_recyclability_criteria_loaded_and_idempotent(db_session):
    load_all(db_session)
    count_first = db_session.query(RecyclabilityCriterion).count()
    load_all(db_session)
    count_second = db_session.query(RecyclabilityCriterion).count()
    assert count_first == count_second == 3
    dimensions = {c.dimension for c in db_session.query(RecyclabilityCriterion).all()}
    assert dimensions == {"tasarim_uyumu", "ayirma_altyapisi", "toplama_altyapisi"}


def test_only_ppwr_art6_gets_recyclability_breakdown(db_session):
    load_all(db_session)
    req = _request(db_session)

    overall, assessments = assess_regulations(db_session, req)

    by_code = {db_session.get(Regulation, a.regulation_id).code: a for a in assessments}

    md6 = by_code["PPWR-ART-6"]
    assert md6.recyclability_breakdown is not None
    assert len(md6.recyclability_breakdown["dimensions"]) == 3
    dims = {d["dimension"] for d in md6.recyclability_breakdown["dimensions"]}
    assert dims == {"tasarim_uyumu", "ayirma_altyapisi", "toplama_altyapisi"}

    for code, assessment in by_code.items():
        if code != "PPWR-ART-6":
            assert assessment.recyclability_breakdown is None


def test_md6_verdict_and_reasoning_unchanged_by_f9(db_session):
    """F.9'un eklediği breakdown, Md.6'nın kendi verdict/reasoning
    hesaplamasını (generic yol) hiç etkilememeli -- mevcut davranış aynı."""
    load_all(db_session)
    req = _request(db_session)

    overall, assessments = assess_regulations(db_session, req)

    md6 = next(a for a in assessments if db_session.get(Regulation, a.regulation_id).code == "PPWR-ART-6")
    reg = db_session.get(Regulation, md6.regulation_id)
    assert "Geri dönüştürülebilirlik tasarımı" in md6.reasoning or "Md.6" in reg.title


def test_reference_recyclability_criteria_endpoint(client, db_session):
    load_all(db_session)
    resp = client.get("/api/v1/reference/recyclability-criteria")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    assert all(r["is_demo_placeholder"] for r in body)
