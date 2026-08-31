"""Firma Altyapısı (Makine Parkı): kayıtlı üretim hatları, proses tipleri,
katman yapıları, hat-malzeme uyumu. Bu tablo Firma Gerçek Veri Kütüphanesi'ne
aittir (facility_id ile Company/Facility köküne bağlıdır) — Polymer/
Regulation gibi sistem referans tablolarının aksine, buradaki her satır
gerçekten firmanın sahip olduğu bir makineyi temsil eder."""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class ProductionLine(Base, IdMixin, TimestampMixin):
    __tablename__ = "production_lines"

    facility_id: Mapped[str | None] = mapped_column(ForeignKey("facilities.id"), nullable=True)

    name: Mapped[str] = mapped_column(String(160))
    process_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Blown Film Extrusion, Cast Film, Thermoforming, Injection Molding...
    layer_structure: Mapped[str] = mapped_column(String(40))  # "A", "A/B/A", "A/B/C/B/A"...
    layer_count: Mapped[int] = mapped_column(default=1)
    extruder_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    min_micron: Mapped[float] = mapped_column(Float)
    max_micron: Mapped[float] = mapped_column(Float)
    min_gsm: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_gsm: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_dosage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_dosage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    line_speed_m_min: Mapped[float] = mapped_column(Float, default=0.0)
    supported_packaging_types: Mapped[list] = mapped_column(default=list)
    energy_kwh_per_kg: Mapped[float] = mapped_column(Float, default=0.0)
    active: Mapped[bool] = mapped_column(default=True)

    # Gerçek makine entegrasyonu bu fazda yok; alanlar gelecekteki PLC/OPC-UA/
    # Modbus TCP/API bağlantısı için tutulur, MVP'de hepsi False kalır.
    plc_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    opc_ua_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    modbus_tcp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    api_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    material_compatibility: Mapped[list["LineMaterialCompatibility"]] = relationship(
        back_populates="line"
    )


class LineMaterialCompatibility(Base, IdMixin, TimestampMixin):
    __tablename__ = "line_material_compatibility"

    line_id: Mapped[str] = mapped_column(ForeignKey("production_lines.id"))
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"))
    max_ratio_pct: Mapped[float] = mapped_column(Float, default=100.0)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    line: Mapped["ProductionLine"] = relationship(back_populates="material_compatibility")
