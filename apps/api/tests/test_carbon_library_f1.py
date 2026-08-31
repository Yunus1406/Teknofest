"""Faz F.1 — Karbon Veri Kütüphanesi genişletmesi: `factor_type` ayrımı
(malzeme/elektrik/dogalgaz/nakliye). Mevcut malzeme EF'lerinin davranışı
(Faz B.2/carbon.py) DEĞİŞMEDİ -- sadece yeni bir sınıflandırma alanı eklendi."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.knowledge_base.loader import load_all
from app.main import app
from app.models.knowledge import CarbonEmissionFactor


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_material_ef_rows_default_to_malzeme_factor_type(db_session):
    load_all(db_session)
    row = db_session.query(CarbonEmissionFactor).filter_by(material_key="PP Virgin Enjeksiyon Sınıfı").one()
    assert row.factor_type == "malzeme"


def test_electricity_and_natural_gas_ef_rows_loaded_with_correct_factor_type(db_session):
    load_all(db_session)
    electricity = db_session.query(CarbonEmissionFactor).filter_by(material_key="Elektrik (TR Şebeke Karışımı)").one()
    assert electricity.factor_type == "elektrik"
    assert electricity.unit == "kg_co2e_per_kwh"
    assert electricity.is_demo_placeholder is True

    gas = db_session.query(CarbonEmissionFactor).filter_by(material_key="Doğalgaz (Yakma)").one()
    assert gas.factor_type == "dogalgaz"


def test_no_transport_ef_seeded_stays_undefined(db_session):
    """Nakliye EF'i için gerçek/tahmini bir kaynak henüz seçilmedi -- hiçbir
    satır seed edilmemeli (uydurma bir sayı eklenmedi, bkz. YAML yorum)."""
    load_all(db_session)
    transport_rows = db_session.query(CarbonEmissionFactor).filter_by(factor_type="nakliye").all()
    assert transport_rows == []


def test_kb_carbon_emission_factors_endpoint_exposes_factor_type(client, db_session):
    load_all(db_session)
    resp = client.get("/api/v1/kb/carbon-emission-factors")
    assert resp.status_code == 200
    body = resp.json()
    factor_types = {row["factor_type"] for row in body}
    assert "malzeme" in factor_types
    assert "elektrik" in factor_types
    assert "dogalgaz" in factor_types
