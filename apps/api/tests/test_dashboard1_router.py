"""Faz E.5 — GET /dashboard1/summary'nin yeni firma bazlı alanları
(company_name/facility_name/sayaçlar/active_optimizations) doğru şekilde
sarmaladığını doğrular. Aggregasyon mantığının kendisi
tests/test_dashboard_aggregation.py'de test edilir; burada sadece
router'ın bu sonuçları doğru response alanlarına yerleştirdiği kontrol edilir."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.company import Company, Facility
from app.models.infrastructure import ProductionLine
from app.models.optimization import OptimizationRun
from app.models.recipe import PackagingRequest


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_dashboard_summary_includes_company_overview_and_active_optimizations(client, db_session):
    company = Company(name="Router Test A.Ş.")
    db_session.add(company)
    db_session.flush()
    db_session.add(Facility(company_id=company.id, name="Router Test Tesis"))
    db_session.add(ProductionLine(name="Hat-1", layer_structure="A", layer_count=1, min_micron=10, max_micron=100, active=True))

    req = PackagingRequest(
        packaging_type="test", usage_area="x", product="x", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
    )
    db_session.add(req)
    db_session.flush()
    db_session.add(OptimizationRun(packaging_request_id=req.id, parameters={}))
    db_session.commit()

    resp = client.get("/api/v1/dashboard1/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["company_name"] == "Router Test A.Ş."
    assert body["facility_name"] == "Router Test Tesis"
    assert body["active_line_count"] == 1
    assert body["registered_material_count"] == 0
    assert body["registered_sku_count"] == 0
    assert body["active_optimizations"] == 1


def test_dashboard_summary_company_fields_null_without_company(client):
    resp = client.get("/api/v1/dashboard1/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["company_name"] is None
    assert body["facility_name"] is None
    assert body["active_optimizations"] == 0
