"""PPWR Kural Kütüphanesi (Sistem Referans Kütüphanesi — company_id YOK,
herkese ait). Faz B.8 — bir `Regulation`'ın (ör. PPWR-ART-7) madde numarası,
gereklilik metni, kategori/yıl kırılımı ve istisna metni artık
`packaging_service._assess_single_regulation`'daki Python if/elif
dallarında HARDCODE değil, burada VERİ olarak tutulur. Yeni bir madde/
kategori eklemek artık yeni bir kod dalı değil, yeni bir satır gerektirir
(bkz. app/knowledge_base/data/regulation_requirements.yaml).

Bir `Regulation` birden fazla `RegulationRequirement` satırına sahip
olabilir — ör. PPWR Md.7'nin kategori+yıl başına ayrı satırı (2030->%10,
2040->%25); tek bir madde tek satırla da temsil edilebilir (ör. Md.6)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class RegulationRequirement(Base, IdMixin, TimestampMixin):
    __tablename__ = "regulation_requirements"

    regulation_id: Mapped[str] = mapped_column(ForeignKey("regulations.id"))
    regulation_no: Mapped[str] = mapped_column(String(60))  # ör. "EU 2025/40"
    article: Mapped[str] = mapped_column(String(60))  # ör. "Md.10 / Ek IV"
    # Faz G.2 — "Md.10"tan AYRI, o maddenin bir alt fıkrası/eki varsa (ör.
    # Md.5(5) için "5. fıkra", Md.10 için "Ek IV"). Bilinmiyorsa/tek bir
    # bölünmemiş madde ise None kalır -- uydurma bir alt madde numarası
    # ASLA atanmaz.
    sub_article: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # None = tüm ambalaj kategorileri için geçerli; dolu ise (ör. PPWR Md.7
    # gibi) kategoriye özgü bir hedef/gereklilik.
    packaging_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requirement_text: Mapped[str] = mapped_column(String(2000))
    pcr_only: Mapped[bool] = mapped_column(Boolean, default=False)
    exception_text: Mapped[str | None] = mapped_column(String(400), nullable=True)
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Plan listesinde açıkça yok ama zorunlu: DB satırından otomatik
    # değerlendirme üretebilmek için bir "bu madde karşılanmazsa/doğrulanmazsa
    # varsayılan karar ne" bilgisi gerekir — yoksa verdict hesaplama kod
    # dalı olarak kalmaya devam ederdi (bkz. packaging_service.py
    # _assess_single_regulation genel yol).
    default_verdict: Mapped[str] = mapped_column(String(30), default="inceleme_gerekli")

    # --- Faz F.2: yapılandırılmış sayısal eşik ---------------------------
    # Eskiden bu sayılar (ör. "%10 -> 2030, %25 -> 2040") SADECE
    # requirement_text prozasında gömülüydü, sorgulanabilir değildi. Bu iki
    # alan AYNI kaynaktan (requirement_text'in zaten taşıdığı sayı) türetilir
    # -- uydurma yeni bir rakam DEĞİL, mevcut prozanın yapılandırılmış hali.
    threshold_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Faz G.2 — ORM'nin otomatik yönettiği `updated_at` (TimestampMixin) HER
    # satır mutasyonunda değişir (ör. bir migration/reseed sırasında), bu
    # yüzden "kaynağın gerçekten ne zaman bir insan tarafından doğrulandığı"
    # bilgisini TAŞIYAMAZ. Bu alan AYRI ve SADECE seed verisinden/manuel bir
    # incelemeden set edilir; bilinmiyorsa None kalır.
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    regulation: Mapped["Regulation"] = relationship()  # noqa: F821
