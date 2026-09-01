"""Faz N.2 (Madde 15) — kullanıcının kendi benchmark verisini girebileceği
CRUD API. Faz F.11'in `BenchmarkReference`'ından (sistem-geneli, kasıtlı
boş) TAMAMEN AYRI: bu company_id'li, kullanıcı tarafından girilen gerçek
veridir. Serbest metin kategori/metrik KABUL EDİLMEZ -- sadece bilinen sabit
kümeler (Aşama 12/Rapor'un karşılaştırması aynı büyüklüğü kıyaslasın diye)."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.company import Company
from app.services import company_benchmark_service


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _company(db):
    c = Company(name="Test Firma N2")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_create_and_list_benchmark_via_service(db_session):
    company = _company(db_session)
    benchmark = company_benchmark_service.create_benchmark(
        db_session, company.id,
        {
            "packaging_category": "plastik_tabak", "metric_name": "karbon_kg_co2_per_kg",
            "value": 1.8, "unit": "kg CO2/kg", "source": "Kendi 2025 üretim ortalamamız",
        },
    )
    assert benchmark.value == 1.8

    listed = company_benchmark_service.list_benchmarks(db_session, company.id)
    assert len(listed) == 1
    assert listed[0].id == benchmark.id


def test_create_rejects_unknown_category(db_session):
    company = _company(db_session)
    with pytest.raises(ValueError, match="bilinmeyen bir ambalaj kategorisi"):
        company_benchmark_service.create_benchmark(
            db_session, company.id,
            {
                "packaging_category": "uydurma_kategori", "metric_name": "karbon_kg_co2_per_kg",
                "value": 1.0, "unit": "kg CO2/kg", "source": "test",
            },
        )


def test_create_rejects_unknown_metric(db_session):
    company = _company(db_session)
    with pytest.raises(ValueError, match="bilinmeyen bir metrik"):
        company_benchmark_service.create_benchmark(
            db_session, company.id,
            {
                "packaging_category": "plastik_tabak", "metric_name": "uydurma_metrik",
                "value": 1.0, "unit": "kg CO2/kg", "source": "test",
            },
        )


def test_delete_removes_row_and_returns_false_for_unknown_id(db_session):
    company = _company(db_session)
    benchmark = company_benchmark_service.create_benchmark(
        db_session, company.id,
        {
            "packaging_category": "sise", "metric_name": "maliyet_tl_per_kg",
            "value": 25.0, "unit": "TL/kg", "source": "test",
        },
    )
    assert company_benchmark_service.delete_benchmark(db_session, company.id, benchmark.id) is True
    assert company_benchmark_service.list_benchmarks(db_session, company.id) == []
    assert company_benchmark_service.delete_benchmark(db_session, company.id, "olmayan-id") is False


def test_delete_does_not_remove_another_companys_benchmark(db_session):
    """Firma izolasyonu: bir firmanın benchmark'ı BAŞKA bir company_id ile silinemez."""
    company_a = _company(db_session)
    company_b = Company(name="Firma B N2")
    db_session.add(company_b)
    db_session.commit()
    db_session.refresh(company_b)

    benchmark = company_benchmark_service.create_benchmark(
        db_session, company_a.id,
        {
            "packaging_category": "kapak", "metric_name": "pcr_orani_pct",
            "value": 30.0, "unit": "%", "source": "test",
        },
    )
    assert company_benchmark_service.delete_benchmark(db_session, company_b.id, benchmark.id) is False
    assert len(company_benchmark_service.list_benchmarks(db_session, company_a.id)) == 1


# --- Gerçek HTTP zinciri (router) -------------------------------------------

def test_http_create_list_delete_roundtrip(client, db_session):
    _company(db_session)

    create_resp = client.post(
        "/api/v1/company/benchmarks",
        json={
            "packaging_category": "esnek_film_ambalaj", "metric_name": "karbon_kg_co2_per_kg",
            "value": 2.1, "unit": "kg CO2/kg", "source": "TÜİK 2024 sektör raporu",
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    assert created["value"] == 2.1
    assert created["created_at"] is not None

    list_resp = client.get("/api/v1/company/benchmarks")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    delete_resp = client.delete(f"/api/v1/company/benchmarks/{created['id']}")
    assert delete_resp.status_code == 204

    list_resp2 = client.get("/api/v1/company/benchmarks")
    assert list_resp2.json() == []


def test_http_create_rejects_unknown_category_with_400(client, db_session):
    _company(db_session)
    resp = client.post(
        "/api/v1/company/benchmarks",
        json={
            "packaging_category": "uydurma", "metric_name": "karbon_kg_co2_per_kg",
            "value": 1.0, "unit": "kg CO2/kg", "source": "test",
        },
    )
    assert resp.status_code == 400


def test_http_benchmarks_require_existing_company(client):
    """Firma profili henüz yoksa -- Faz E.1'in disipliniyle tutarlı --
    404 döner, sessizce boş/uydurma bir kayıt oluşturulmaz."""
    resp = client.get("/api/v1/company/benchmarks")
    assert resp.status_code == 404
