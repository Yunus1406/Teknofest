"""Üretim, canlı takip ve fiziksel doğrulama modelleri.
Faz 1'de production_live_data ve fiziksel test girişleri mock/simüle veriyle
beslenir; şema gerçek üretim entegrasyonuna hazır tasarlanmıştır."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class ProductionOrder(Base, IdMixin, TimestampMixin):
    __tablename__ = "production_orders"

    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"))
    line_id: Mapped[str] = mapped_column(ForeignKey("production_lines.id"))
    status: Mapped[str] = mapped_column(String(30), default="bekliyor")  # ProductionOrderStatus
    scheduled_qty_units: Mapped[int] = mapped_column(default=0)

    # Faz B.6 — opsiyonel üretim geçmişi alanları. Gerçek entegrasyon
    # olmadığından (simülasyon) hepsi nullable; `simulate_live_data`
    # tamamlandığında doldurulur, gerçek PLC/MES entegrasyonunda da aynı
    # alanlar operatör girişi/PLC'den beslenecek şekilde tasarlanmıştır.
    operator: Mapped[str | None] = mapped_column(String(120), nullable=True)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    downtime_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_micron: Mapped[float | None] = mapped_column(Float, nullable=True)
    # {layer_index: {material_id: gerçekleşen_oran_pct}} — reçetenin NOMİNAL
    # katman oranlarından sapmayı gösterir (gerçek üretimde oranlar asla
    # tam nominal değildir); Aşama 12/izlenebilirlik için referans.
    actual_layer_ratios: Mapped[dict] = mapped_column(default=dict)

    live_data: Mapped[list["ProductionLiveData"]] = relationship(back_populates="order")
    physical_tests: Mapped[list["PhysicalTest"]] = relationship(back_populates="order")
    waste_records: Mapped[list["WasteRecord"]] = relationship(back_populates="order")
    recipe = relationship("Recipe")


class ProductionLiveData(Base, IdMixin):
    __tablename__ = "production_live_data"

    production_order_id: Mapped[str] = mapped_column(ForeignKey("production_orders.id"))
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    # produced_qty_units KÜMÜLATİF üretim (üretim emrinin başından bu satıra
    # kadar); period_produced_qty_units bu satırdaki (bir önceki satırdan bu
    # yana) DÖNEMSEL üretim. energy_kwh/waste_kg DÖNEMSEL, cumulative_* alanları
    # KÜMÜLATİF karşılıklarıdır — önceden bu ayrım yoktu, UI'da enerji/fire'ın
    # dönemsel mi kümülatif mi olduğu belirsizdi.
    produced_qty_units: Mapped[int] = mapped_column(default=0)
    period_produced_qty_units: Mapped[int] = mapped_column(default=0)
    material_consumption: Mapped[dict] = mapped_column(default=dict)  # {material_id: kg} (dönemsel)
    line_speed_m_min: Mapped[float] = mapped_column(Float, default=0.0)
    energy_kwh: Mapped[float] = mapped_column(Float, default=0.0)
    cumulative_energy_kwh: Mapped[float] = mapped_column(Float, default=0.0)
    waste_kg: Mapped[float] = mapped_column(Float, default=0.0)
    cumulative_waste_kg: Mapped[float] = mapped_column(Float, default=0.0)
    # Gerçek makine/PLC entegrasyonu bu fazda yok; simüle veri
    # DataSourceType.SIMULASYON_VERISI ile işaretlenir, 'Makineden Alınan'
    # (DataSourceType.MAKINEDEN_ALINAN) yalnızca gerçek entegrasyonda kullanılır.
    source: Mapped[str] = mapped_column(String(40), default="simulasyon_verisi")

    order: Mapped["ProductionOrder"] = relationship(back_populates="live_data")


class WasteRecord(Base, IdMixin, TimestampMixin):
    """Faz B.6 — tipli fire kırılımı (Fire Veri Tabanı). Bu tablo
    `ProductionLiveData.waste_kg` (dönemsel toplam fire) alanının yerini
    ALMAZ — o alan Dashboard 1/10/12'nin mevcut kütle dengesi hesaplarında
    değişmeden kullanılmaya devam eder. `WasteRecord` aynı fireyi TÜRÜNE göre
    kıran ek/tamamlayıcı bir kırılım sağlar (bkz. app/models/enums.py WasteType)."""
    __tablename__ = "waste_records"

    production_order_id: Mapped[str] = mapped_column(ForeignKey("production_orders.id"))
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    waste_type: Mapped[str] = mapped_column(String(40))  # WasteType
    kg: Mapped[float] = mapped_column(Float, default=0.0)
    # Geri kazanılabilir mi (ör. temiz kenar firesi -> PIR/regranül hattına
    # geri döner) yoksa değil mi (ör. kontamine/kalite reddi -> bertaraf).
    recoverable: Mapped[bool] = mapped_column(Boolean, default=False)

    order: Mapped["ProductionOrder"] = relationship(back_populates="waste_records")


class PhysicalTest(Base, IdMixin, TimestampMixin):
    __tablename__ = "physical_tests"

    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"))
    production_order_id: Mapped[str | None] = mapped_column(
        ForeignKey("production_orders.id"), nullable=True
    )
    test_type: Mapped[str] = mapped_column(String(60))
    # kalinlik, gramaj, tensile, elongation, dart_impact, tear, seal
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))
    target_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    test_method: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # ör. "ISO 4593 - mikrometre ölçümü"; hangi standart/yönteme göre ölçüldüğü
    passed: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(40), default="laboratuvar_testi")

    order: Mapped["ProductionOrder"] = relationship(back_populates="physical_tests")


class SustainabilityResult(Base, IdMixin, TimestampMixin):
    __tablename__ = "sustainability_results"

    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"))
    per_1000_units: Mapped[dict] = mapped_column(default=dict)
    # {"virgin_kg":.., "pcr_kg":.., "regranul_kg":.., "karbon_kg_co2":.., "fire_kg":..}
    is_actual: Mapped[bool] = mapped_column(Boolean, default=False)
    # False: aşama 8 "Tahmini", True: aşama 12 "Gerçekleşen"
