"""Faz F.10 + F.11 — Maliyet Referans Kütüphanesi + Benchmark. F.10'un ana
sözleşmesi: firmanın kendi tesis-özel CostFactor'ı HER ZAMAN önceliklidir
(FIRMA_URETIM), sistem referansı (SISTEM_REFERANS) sadece firma o kalemi
girmediyse yedek olarak kullanılır -- F.12'nin resolve_value'su ile.
F.11 (BenchmarkReference) kasıtlı olarak boş; bu bir hata değildir."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.knowledge_base.loader import load_all
from app.main import app
from app.models.company import Company, Facility
from app.models.cost import CostFactor
from app.models.cost_reference import BenchmarkReference, CostReferenceFactor
from app.services.cost_reference_service import resolve_cost_component
from app.services.data_resolution import SourceTier


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def facility(db_session):
    company = Company(name="Test Firma F10")
    db_session.add(company)
    db_session.flush()
    facility = Facility(company_id=company.id, name="Test Tesis F10")
    db_session.add(facility)
    db_session.commit()
    db_session.refresh(facility)
    return facility


# --- F.10: yükleme + idempotency -------------------------------------------

def test_cost_reference_factors_loaded_for_all_six_types(db_session):
    load_all(db_session)
    rows = db_session.query(CostReferenceFactor).all()
    cost_types = {r.cost_type for r in rows}
    assert cost_types == {"elektrik", "dogalgaz", "iscilik", "atik_bertaraf", "geri_kazanim", "makine_saati"}


def test_cost_reference_factor_loader_is_idempotent(db_session):
    load_all(db_session)
    count_first = db_session.query(CostReferenceFactor).count()
    load_all(db_session)
    count_second = db_session.query(CostReferenceFactor).count()
    assert count_first == count_second == 6


# --- F.10: firma > sistem referans önceliği --------------------------------

def test_resolve_cost_component_uses_firm_data_when_present(db_session, facility):
    load_all(db_session)
    db_session.add(CostFactor(facility_id=facility.id, currency="TRY", electricity_rate=3.2, is_demo_placeholder=False, source="Fatura kaydı"))
    db_session.commit()

    resolved = resolve_cost_component(db_session, facility.id, "elektrik")

    assert resolved is not None
    assert resolved.value == 3.2
    assert resolved.tier == SourceTier.FIRMA_URETIM
    assert resolved.is_demo_placeholder is False


def test_resolve_cost_component_falls_back_to_reference_when_firm_data_missing(db_session, facility):
    load_all(db_session)
    # facility var ama gaz oranı hiç girilmemiş (None) -> referansa düşmeli.
    db_session.add(CostFactor(facility_id=facility.id, currency="TRY", electricity_rate=3.2, gas_rate=None, is_demo_placeholder=False))
    db_session.commit()

    resolved = resolve_cost_component(db_session, facility.id, "dogalgaz")

    assert resolved is not None
    assert resolved.tier == SourceTier.SISTEM_REFERANS
    assert resolved.value == pytest.approx(20.0)  # (15+25)/2
    assert resolved.is_demo_placeholder is True


def test_resolve_cost_component_none_when_neither_source_has_data(db_session):
    """Referans kütüphanesi hiç yüklenmemiş ve facility de yoksa -- uydurma
    bir sayı ASLA döndürülmez, None döner."""
    resolved = resolve_cost_component(db_session, None, "elektrik")
    assert resolved is None


# --- F.11: kasıtlı olarak boş -----------------------------------------------

def test_benchmark_reference_yaml_is_intentionally_empty(db_session):
    load_all(db_session)
    count = db_session.query(BenchmarkReference).count()
    assert count == 0


# --- Uç noktalar ------------------------------------------------------------

def test_reference_cost_benchmarks_endpoint(client, db_session):
    load_all(db_session)
    resp = client.get("/api/v1/reference/cost-benchmarks")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 6
    assert all(r["is_demo_placeholder"] for r in body)


def test_reference_benchmarks_endpoint_returns_empty_list_not_error(client, db_session):
    load_all(db_session)
    resp = client.get("/api/v1/reference/benchmarks")
    assert resp.status_code == 200
    assert resp.json() == []
