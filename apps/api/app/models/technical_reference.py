"""Faz F.5 + F.7 + F.8 — Polimer Teknik + Proses + Ambalaj Yapısı Referans
Kütüphaneleri (Sistem Referans Kütüphanesi — company_id YOK). Üçü de genel,
firma-bağımsız TİPİK aralık/bilgi taşır -- Faz E'deki firma-özel hammadde
kartından (Material), makine kaydından (ProductionLine) ve ürün kaydından
(ProductSku.layer_structure) TAMAMEN AYRIDIR; bir firma kendi verisini
girmediğinde ya da genel karşılaştırma yapmak istediğinde kullanılır."""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class PolymerTechnicalReference(Base, IdMixin, TimestampMixin):
    """Faz F.5 — bir polimer ailesinin (Polymer) TİPİK mekanik/termal özellik
    aralığı. Bir polimer birden fazla satıra sahip olabilir (her satır bir
    property_name -- ör. "tensile_strength_mpa", "density_g_cm3")."""

    __tablename__ = "polymer_technical_references"

    polymer_id: Mapped[str] = mapped_column(ForeignKey("polymers.id"))
    property_name: Mapped[str] = mapped_column(String(60))
    typical_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    typical_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20))
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    is_demo_placeholder: Mapped[bool] = mapped_column(Boolean, default=True)

    polymer: Mapped["Polymer"] = relationship()  # noqa: F821


class ProcessReference(Base, IdMixin, TimestampMixin):
    """Faz F.7 — bir proses tipinin (blown film/cast film/thermoforming/
    injection molding...) TİPİK parametre aralığı. `process_type` serbest
    metin -- Faz E.2'deki `ProductionLine.process_type` ile aynı sözlüğü
    (MACHINE_CLASSES) kullanır ama DB kısıtı yok."""

    __tablename__ = "process_references"

    process_type: Mapped[str] = mapped_column(String(60))
    parameter_name: Mapped[str] = mapped_column(String(60))
    typical_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    typical_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20))
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    is_demo_placeholder: Mapped[bool] = mapped_column(Boolean, default=True)


class LayerStructureReference(Base, IdMixin, TimestampMixin):
    """Faz F.8 — yaygın bir katman yapısının (A, A/B/A, ABC, ABCBA...) TİPİK
    kullanım alanı ve bariyer özelliği. Sayısal bir aralık değil, serbest
    metin -- bu bilgi doğası gereği tanımlayıcı/niteliksel."""

    __tablename__ = "layer_structure_references"

    structure_pattern: Mapped[str] = mapped_column(String(40), unique=True)
    typical_usage: Mapped[str] = mapped_column(String(400))
    barrier_properties: Mapped[str] = mapped_column(String(400))
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    is_demo_placeholder: Mapped[bool] = mapped_column(Boolean, default=True)
