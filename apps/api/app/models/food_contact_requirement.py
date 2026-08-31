"""Faz F.3 — Gıda Temas Mevzuatı Kütüphanesi (Sistem Referans Kütüphanesi —
company_id YOK). Bugüne kadar sistemde gıda teması SADECE `Material.
food_contact_eligible: bool` + serbest metin `certification_status`/
`regulatory_document_ref` olarak temsil ediliyordu -- migrasyon limiti gibi
YAPILANDIRILMIŞ hiçbir alan yoktu. Bu tablo EU 1935/2004 çerçeve tüzüğü ve
EU 10/2011 (plastik FCM) gibi spesifik mevzuatın migrasyon limitlerini ve
PCR'a özgü ek gerekliliklerini (dekontaminasyon süreç onayı) yapılandırılmış
veri olarak tutar."""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class FoodContactRequirement(Base, IdMixin, TimestampMixin):
    __tablename__ = "food_contact_requirements"

    regulation_id: Mapped[str] = mapped_column(ForeignKey("regulations.id"))
    requirement_type: Mapped[str] = mapped_column(String(40))
    # genel_migrasyon / spesifik_migrasyon / pcr_dekontaminasyon
    substance: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # spesifik_migrasyon satırlarında madde adı; genel/prosedürel satırlarda None.
    limit_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    limit_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Sayısal bir limit yoksa (ör. pcr_dekontaminasyon prosedürel bir
    # gerekliliktir, tek bir sayıya indirgenemez) İKİSİ de None kalır --
    # uydurma bir "temsili" sayı ASLA atanmaz.
    applies_to_pcr: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    is_demo_placeholder: Mapped[bool] = mapped_column(Boolean, default=True)

    regulation: Mapped["Regulation"] = relationship()  # noqa: F821
