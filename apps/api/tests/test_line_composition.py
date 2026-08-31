"""Faz G.3 — "Kayıtlı Makineden Hat Oluştur": `derive_composite_line_defaults`
kesişim/min/AND türetme mantığını, DB'ye hiç dokunmadan (saf fonksiyon)
doğrular. Ayrıca `POST /production-lines`'ın yeni `component_line_ids`
alanını doğru kaydettiği gerçek bir HTTP round-trip ile kanıtlanır."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.infrastructure import ProductionLine
from app.services.line_composition import derive_composite_line_defaults


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _line(**kwargs) -> ProductionLine:
    defaults = dict(
        name="Test", layer_structure="A", layer_count=1, min_micron=10, max_micron=100,
        supported_packaging_types=[],
    )
    defaults.update(kwargs)
    return ProductionLine(**defaults)


def test_empty_components_returns_empty_dict():
    assert derive_composite_line_defaults([]) == {}


def test_min_max_micron_uses_intersection():
    a = _line(id="a", min_micron=10, max_micron=90)
    b = _line(id="b", min_micron=30, max_micron=70)
    result = derive_composite_line_defaults([a, b])
    assert result["min_micron"] == 30  # max of mins
    assert result["max_micron"] == 70  # min of maxes


def test_line_speed_uses_slowest_component():
    a = _line(id="a", line_speed_m_min=150.0)
    b = _line(id="b", line_speed_m_min=60.0)
    result = derive_composite_line_defaults([a, b])
    assert result["line_speed_m_min"] == 60.0


def test_pcr_capable_true_only_when_all_components_true():
    a = _line(id="a", pcr_capable=True)
    b = _line(id="b", pcr_capable=True)
    assert derive_composite_line_defaults([a, b])["pcr_capable"] is True

    c = _line(id="c", pcr_capable=False)
    assert derive_composite_line_defaults([a, c])["pcr_capable"] is False


def test_pcr_capable_none_when_no_component_has_data():
    a = _line(id="a", pcr_capable=None)
    b = _line(id="b", pcr_capable=None)
    result = derive_composite_line_defaults([a, b])
    assert "pcr_capable" not in result  # uydurma bir kabiliyet iddiası yok


def test_suitable_polymer_codes_uses_intersection():
    a = _line(id="a", suitable_polymer_codes=["PE", "PP", "PET"])
    b = _line(id="b", suitable_polymer_codes=["PP", "PET"])
    result = derive_composite_line_defaults([a, b])
    assert result["suitable_polymer_codes"] == ["PET", "PP"]


def test_layer_structure_taken_from_extrusion_component():
    ext = _line(id="ext", process_type="Blown Film Extrusion", layer_structure="A/B/A", layer_count=3)
    doser = _line(id="doser", process_type="Gravimetric Dosing", layer_structure="A", layer_count=1)
    result = derive_composite_line_defaults([ext, doser])
    assert result["layer_structure"] == "A/B/A"
    assert result["layer_count"] == 3


def test_layer_structure_absent_when_no_extrusion_component():
    doser = _line(id="doser", process_type="Gravimetric Dosing")
    result = derive_composite_line_defaults([doser])
    assert "layer_structure" not in result


def test_component_line_ids_and_name_are_recorded():
    a = _line(id="line-a", name="Ekstrüder-1")
    b = _line(id="line-b", name="Gravimetrik Dozaj-1")
    result = derive_composite_line_defaults([a, b])
    assert result["component_line_ids"] == ["line-a", "line-b"]
    assert result["name"] == "Ekstrüder-1 + Gravimetrik Dozaj-1"


def test_capacity_uses_bottleneck_minimum():
    a = _line(id="a", nominal_capacity_kg_year=500_000)
    b = _line(id="b", nominal_capacity_kg_year=200_000)
    result = derive_composite_line_defaults([a, b])
    assert result["nominal_capacity_kg_year"] == 200_000


# --- Gerçek HTTP round-trip: component_line_ids doğru kaydediliyor ---------

def test_create_production_line_stores_component_line_ids(client, db_session):
    part_a = ProductionLine(name="Ekstrüder-1", layer_structure="A", layer_count=1, min_micron=10, max_micron=100)
    part_b = ProductionLine(name="Gravimetrik Dozaj-1", layer_structure="A", layer_count=1, min_micron=10, max_micron=100)
    db_session.add_all([part_a, part_b])
    db_session.commit()
    db_session.refresh(part_a)
    db_session.refresh(part_b)

    resp = client.post(
        "/api/v1/production-lines",
        json={
            "name": "Ekstrüder-1 + Gravimetrik Dozaj-1", "layer_structure": "A", "min_micron": 10, "max_micron": 100,
            "component_line_ids": [part_a.id, part_b.id],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["component_line_ids"] == [part_a.id, part_b.id]


def test_create_production_line_without_components_leaves_field_none(client):
    resp = client.post(
        "/api/v1/production-lines",
        json={"name": "Tekil Hat", "layer_structure": "A", "min_micron": 10, "max_micron": 100},
    )
    assert resp.status_code == 200
    assert resp.json()["component_line_ids"] is None
