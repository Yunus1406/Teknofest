"""Faz B.1 — Company/Facility kökü + Makine Parkı (ProductionLine) genişletmesi."""
from app.models.company import Company, Facility
from app.models.infrastructure import ProductionLine
from app.schemas.infrastructure import ProductionLineOut


def test_company_facility_relationship(db_session):
    company = Company(name="Test Firma A.Ş.")
    db_session.add(company)
    db_session.flush()
    facility = Facility(company_id=company.id, name="Test Tesis", address="Test Adres")
    db_session.add(facility)
    db_session.commit()
    db_session.refresh(company)

    assert facility.company_id == company.id
    assert company.facilities[0].id == facility.id


def test_production_line_belongs_to_facility_and_carries_machine_park_fields(db_session):
    company = Company(name="Test Firma A.Ş.")
    db_session.add(company)
    db_session.flush()
    facility = Facility(company_id=company.id, name="Test Tesis")
    db_session.add(facility)
    db_session.flush()

    line = ProductionLine(
        facility_id=facility.id,
        name="Hat-Test",
        process_type="Blown Film Extrusion",
        extruder_count=2,
        layer_structure="A/B/A",
        layer_count=3,
        min_micron=20,
        max_micron=120,
        max_width_mm=1500,
        min_dosage_pct=0,
        max_dosage_pct=50,
        supported_packaging_types=["esnek_film_ambalaj"],
    )
    db_session.add(line)
    db_session.commit()
    db_session.refresh(line)

    assert line.facility_id == facility.id
    assert line.process_type == "Blown Film Extrusion"
    # MVP'de gerçek entegrasyon yok -> hepsi varsayılan False olmalı.
    assert line.plc_enabled is False
    assert line.opc_ua_enabled is False
    assert line.modbus_tcp_enabled is False
    assert line.api_enabled is False


def test_production_line_out_schema_serializes_new_fields(db_session):
    company = Company(name="Test Firma A.Ş.")
    db_session.add(company)
    db_session.flush()
    facility = Facility(company_id=company.id, name="Test Tesis")
    db_session.add(facility)
    db_session.flush()
    line = ProductionLine(
        facility_id=facility.id, name="Hat-Test", process_type="Injection Molding",
        layer_structure="A", layer_count=1, min_micron=800, max_micron=2500,
        supported_packaging_types=["kapak"],
    )
    db_session.add(line)
    db_session.commit()
    db_session.refresh(line)

    out = ProductionLineOut.model_validate(line)
    assert out.facility_id == facility.id
    assert out.process_type == "Injection Molding"
    assert out.plc_enabled is False


def test_production_line_facility_id_is_optional_for_backward_compatibility(db_session):
    """Faz A'daki mevcut satırlar facility_id olmadan da geçerli kalmalı --
    şema geriye dönük uyumlu (nullable FK)."""
    line = ProductionLine(
        name="Hat-Eski", layer_structure="A", layer_count=1, min_micron=10, max_micron=100,
        supported_packaging_types=[],
    )
    db_session.add(line)
    db_session.commit()
    db_session.refresh(line)
    assert line.facility_id is None
