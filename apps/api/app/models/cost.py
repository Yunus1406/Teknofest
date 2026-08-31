"""Maliyet Veri Tabanı (Firma Gerçek Veri Kütüphanesi) — tesis bazlı birim
maliyet kalemleri. Faz B.7 kapsamı SADECE saklama + basit görünürlüktür;
`app/optimization/scorer.py`'nin mevcut malzeme-bazlı maliyet skoruna
(candidate.cost_per_kg) entegre ETMEK kapsam dışıdır — bu ayrı, daha büyük
bir iyileştirme olurdu (bkz. Faz B planı B.7)."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class CostFactor(Base, IdMixin, TimestampMixin):
    __tablename__ = "cost_factors"

    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id"))
    currency: Mapped[str] = mapped_column(String(10), default="TRY")
    # Birimler (kayıt başına tek para birimi ile tutarlı): electricity_rate
    # (para/kWh), gas_rate (para/m3), labor_rate (para/saat),
    # waste_disposal_cost (para/kg bertaraf), recovery_cost (para/kg geri
    # kazanım — PIR/PCR'a dönüştürme maliyeti), machine_hour_rate (para/saat).
    electricity_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    gas_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    labor_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    waste_disposal_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    recovery_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    machine_hour_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    effective_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    # CarbonEmissionFactor'daki aynı ilke: gerçek sözleşme/fatura verisi
    # yoksa bu True kalır ve kaynak açıkça "DEMO/VARSAYIMSAL" işaretlenir —
    # UI hiçbir zaman demo maliyet verisini gerçekmiş gibi sunmamalı.
    is_demo_placeholder: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)

    facility: Mapped["Facility"] = relationship()  # noqa: F821
