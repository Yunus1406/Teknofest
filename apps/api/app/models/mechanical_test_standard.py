"""Faz F.6 — Mekanik Test Standartları Kütüphanesi (Sistem Referans
Kütüphanesi — company_id YOK). `test_targets.py::suggested_physical_test_
targets` şimdiye kadar tensile/elongation/dart_impact/tear/seal için hiçbir
sayısal öneri vermiyordu (bilgi tabanında referans veri yoktu) -- bu tablo o
boşluğu dolduruyor.

ÖNEMLİ: bu SADECE bir ÖNERİ kütüphanesidir. Faz D.2'nin "gerçek ölçüm +
tanımlı kriter olmadan Geçti diyemezsin" kuralı DEĞİŞMEDİ --
`PhysicalTest.target_min/target_max` (gerçek geçme/kalma kriteri) bu
tablodan OTOMATİK doldurulmaz; `suggested_physical_test_targets` bu satırları
ayrı, açıkça "öneri" etiketli `suggested_min/suggested_max` alanlarına
taşır (bkz. app/services/test_targets.py)."""
from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class MechanicalTestStandard(Base, IdMixin, TimestampMixin):
    __tablename__ = "mechanical_test_standards"

    test_type: Mapped[str] = mapped_column(String(40))
    # tensile / elongation / dart_impact / tear / seal — bkz.
    # app/services/test_targets.py _MECHANICAL_TEST_UNITS ile aynı sözlük.
    standard_name: Mapped[str] = mapped_column(String(60))  # ör. "ASTM D882"
    unit: Mapped[str] = mapped_column(String(20))
    packaging_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # None = tüm ambalaj kategorileri için geçerli (RegulationRequirement'daki
    # aynı kural).
    typical_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    typical_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    is_demo_placeholder: Mapped[bool] = mapped_column(Boolean, default=True)
