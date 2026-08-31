"""Faz F.5 + F.7 + F.8 — Polimer Teknik + Proses + Ambalaj Yapısı Referans
Kütüphaneleri. Üçü de yeni, bağımsız sistem-referans tablosu; hiçbiri
mevcut Faz E firma-özel kayıtlarına (Material/ProductionLine/ProductSku)
DOKUNMAZ, sadece PARALEL bir genel kıyaslama kütüphanesi kurar."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.knowledge_base.loader import load_all
from app.main import app
from app.models.knowledge import Polymer
from app.models.technical_reference import (
    LayerStructureReference,
    PolymerTechnicalReference,
    ProcessReference,
)


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# --- F.5: Polimer Teknik Referans ----------------------------------------

def test_pp_polymer_technical_reference_rows_loaded(db_session):
    load_all(db_session)
    pp = db_session.query(Polymer).filter_by(code="PP").one()
    rows = db_session.query(PolymerTechnicalReference).filter_by(polymer_id=pp.id).all()
    by_prop = {r.property_name: r for r in rows}
    assert by_prop["tensile_strength_mpa"].typical_min == 25
    assert by_prop["tensile_strength_mpa"].typical_max == 40
    assert by_prop["tensile_strength_mpa"].unit == "MPa"
    assert by_prop["tensile_strength_mpa"].is_demo_placeholder is True


def test_polymer_technical_reference_loader_is_idempotent(db_session):
    load_all(db_session)
    count_first = db_session.query(PolymerTechnicalReference).count()
    load_all(db_session)
    count_second = db_session.query(PolymerTechnicalReference).count()
    assert count_first == count_second == 15  # 5 polimer x 3 özellik


# --- F.7: Proses Referans -------------------------------------------------

def test_blown_film_process_reference_rows_loaded(db_session):
    load_all(db_session)
    rows = db_session.query(ProcessReference).filter_by(process_type="Blown Film Extrusion").all()
    by_param = {r.parameter_name: r for r in rows}
    assert by_param["melt_temperature_c"].typical_min == 160
    assert by_param["melt_temperature_c"].typical_max == 220
    assert by_param["line_speed_m_min"].unit == "m_min"


def test_process_reference_loader_is_idempotent(db_session):
    load_all(db_session)
    count_first = db_session.query(ProcessReference).count()
    load_all(db_session)
    count_second = db_session.query(ProcessReference).count()
    assert count_first == count_second == 8  # 4 proses x 2 parametre


# --- F.8: Ambalaj Yapısı Referans ------------------------------------------

def test_layer_structure_reference_rows_loaded(db_session):
    load_all(db_session)
    aba = db_session.query(LayerStructureReference).filter_by(structure_pattern="A/B/A").one()
    assert "esnek film" in aba.typical_usage.lower()
    assert aba.barrier_properties != ""


def test_layer_structure_reference_loader_is_idempotent(db_session):
    load_all(db_session)
    count_first = db_session.query(LayerStructureReference).count()
    load_all(db_session)
    count_second = db_session.query(LayerStructureReference).count()
    assert count_first == count_second == 4


# --- Yeni /reference/* uçları --------------------------------------------

def test_reference_polymer_technical_endpoint(client, db_session):
    load_all(db_session)
    resp = client.get("/api/v1/reference/polymer-technical")
    assert resp.status_code == 200
    assert len(resp.json()) == 15


def test_reference_process_parameters_endpoint(client, db_session):
    load_all(db_session)
    resp = client.get("/api/v1/reference/process-parameters")
    assert resp.status_code == 200
    assert len(resp.json()) == 8


def test_reference_layer_structures_endpoint(client, db_session):
    load_all(db_session)
    resp = client.get("/api/v1/reference/layer-structures")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 4
    assert {r["structure_pattern"] for r in body} == {"A", "A/B/A", "ABC", "ABCBA"}
