"""Faz F.10 + F.11 — Maliyet Referans Kütüphanesi + Benchmark/Sektör
Karşılaştırma Verisi (Sistem Referans Kütüphanesi — company_id YOK). Faz
B.7'nin `CostFactor`'ından (`app/models/cost.py`) AYRI: o tesis-özel firma
gerçek veri kütüphanesidir (facility_id FK taşır), bunlar sistem-genel
YEDEK/gösterge değerleridir -- bir firma kendi `CostFactor` kaydını
girmediğinde referans olarak kullanılabilir (bkz.
app/services/cost_reference_service.py, F.12'nin resolve_value'su ile)."""
from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class CostReferenceFactor(Base, IdMixin, TimestampMixin):
    __tablename__ = "cost_reference_factors"

    cost_type: Mapped[str] = mapped_column(String(40), unique=True)
    # elektrik / dogalgaz / iscilik / atik_bertaraf / geri_kazanim / makine_saati
    # -- app/models/cost.py'nin CostFactor alanlarıyla (electricity_rate,
    # gas_rate, labor_rate, waste_disposal_cost, recovery_cost,
    # machine_hour_rate) BİREBİR eşleşir.
    typical_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    typical_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(10), default="TRY")
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    geography: Mapped[str | None] = mapped_column(String(80), nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    is_demo_placeholder: Mapped[bool] = mapped_column(Boolean, default=True)


class BenchmarkReference(Base, IdMixin, TimestampMixin):
    """Faz F.11 — Ambalaj türü bazında sektör ortalaması referansları. Gerçek
    bir kaynak bulunmadığı için bu MVP'de KASITLI OLARAK boş/neredeyse boş
    seed edilir (bkz. knowledge_base/data/benchmark_reference.yaml) -- uydurma
    bir sektör ortalaması ÜRETİLMEZ; F.13 bu kategoriyi "Henüz referans veri
    girilmedi" olarak göstermelidir."""

    __tablename__ = "benchmark_references"

    packaging_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metric_name: Mapped[str] = mapped_column(String(60))
    # ör. "tipik_pcr_orani", "tipik_kalinlik_mikron", "tipik_karbon_yogunlugu"
    typical_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20))
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    is_demo_placeholder: Mapped[bool] = mapped_column(Boolean, default=True)
