"""Dijital Ürün Pasaportu (Faz C.1) — her DOĞRULANMIŞ reçete için kalıcı,
versiyonlanan kimlik. Bu tablo sadece KİMLİK + VERSİYON bilgisini saklar;
malzeme/çevresel/teknik/mevzuat İÇERİĞİ burada DONDURULMAZ — her okuma
anında `app/services/passport_service.py` tarafından ilgili reçeteden canlı
hesaplanır (Faz A/B'nin 'tek doğruluk kaynağı' ilkesiyle tutarlı — pasaport
verisi, dashboard'ların gösterdiği veriden ASLA sapamaz).

Reçete yeniden doğrulandığında (yeni bir V(n+1) `is_verified=True` olduğunda)
YENİ bir satır (revision+1) açılır, öncekiler asla üzerine yazılmaz —
Rev.1 -> Rev.2 zinciri `previous_passport_id` ile kurulur."""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class DigitalProductPassport(Base, IdMixin, TimestampMixin):
    __tablename__ = "digital_product_passports"

    passport_no: Mapped[str] = mapped_column(String(40), unique=True)  # "DPP-2026-000018"
    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"))
    # Aynı ürün/reçete soyunu gruplamak için: SKU varsa onunla, yoksa (bkz.
    # passport_service._group_key) packaging_request_id ile gruplanır — bu
    # sütun sadece SKU varsa dolu, gruplama mantığının TEK kaynağı değildir.
    sku_id: Mapped[str | None] = mapped_column(ForeignKey("product_skus.id"), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    previous_passport_id: Mapped[str | None] = mapped_column(
        ForeignKey("digital_product_passports.id"), nullable=True
    )

    recipe = relationship("Recipe")
    sku = relationship("ProductSku")
    previous: Mapped["DigitalProductPassport | None"] = relationship(
        remote_side="DigitalProductPassport.id"
    )
