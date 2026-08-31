"""Faz F.9 — Geri Dönüştürülebilirlik Değerlendirme Kriterleri (Sistem
Referans Kütüphanesi — company_id YOK). Faz A'da basitleştirilen "uygun/
uygun değil" tek kutusunu, PPWR'nin GERÇEK çok boyutlu yaklaşımına (tasarım
kriteri + ayrıştırma altyapısı + toplama altyapısı) daha yakın, nüanslı bir
kırılıma taşır -- Dashboard 3'ün mevcut verdict/badge görünümü DEĞİŞMEZ, bu
sadece PPWR-ART-6 (Md.6) değerlendirmesine EK bir bilgi katmanıdır (bkz.
app/services/packaging_service.py `_recyclability_breakdown`)."""
from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class RecyclabilityCriterion(Base, IdMixin, TimestampMixin):
    __tablename__ = "recyclability_criteria"

    packaging_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # None = tüm ambalaj kategorileri için geçerli (RegulationRequirement'daki
    # aynı kural).
    dimension: Mapped[str] = mapped_column(String(40))
    # tasarim_uyumu / ayirma_altyapisi / toplama_altyapisi
    criterion_text: Mapped[str] = mapped_column(String(500))
    weight_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Boyutun genel değerlendirmedeki temsili ağırlığı -- kaynaklı bir
    # metodoloji YOK, is_demo_placeholder ile açıkça işaretlenir.

    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    is_demo_placeholder: Mapped[bool] = mapped_column(Boolean, default=True)
