"""Faz F.4 — Kimyasal Kısıtlar Kütüphanesi (Sistem Referans Kütüphanesi —
company_id YOK). PFAS (PPWR Md.5(5)) gibi kısıtların sayısal limitleri
eskiden `regulations.yaml`'daki `Regulation.criteria` dict'inde duruyordu ama
HİÇBİR Python kodu bu dict'i okumuyordu (yazılıp hiç okunmayan "dekoratif"
veri) -- `packaging_service._assess_single_regulation`'ın PPWR-ART-5 dalı
sadece sabit bir metin döndürüyordu. Bu tablo o sayıları GERÇEKTEN
sorgulanabilir/okunabilir hale getirir; aynı kaynaktan taşınır, uydurulmaz."""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class ChemicalRestriction(Base, IdMixin, TimestampMixin):
    __tablename__ = "chemical_restrictions"

    substance_group: Mapped[str] = mapped_column(String(60))  # ör. "PFAS", "agir_metal"
    restriction_type: Mapped[str] = mapped_column(String(60))
    # ör. "tekil_madde_siniri" / "toplam_hedef" / "toplam_sinir"
    limit_value: Mapped[float] = mapped_column(Float)
    limit_unit: Mapped[str] = mapped_column(String(20))  # ör. "ppb", "ppm"
    food_contact_only: Mapped[bool] = mapped_column(Boolean, default=True)
    regulation_id: Mapped[str | None] = mapped_column(ForeignKey("regulations.id"), nullable=True)

    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    # Faz F planındaki genel disiplin: hukuki/laboratuvar doğrulaması olmayan
    # hiçbir rakam "kaynaklı/gerçek" etiketiyle sunulmaz -- bilinen bir AB
    # tüzük rakamı olsa bile (bkz. app/services/carbon.py'nin aynı temkinli
    # disiplini).
    is_demo_placeholder: Mapped[bool] = mapped_column(Boolean, default=True)

    regulation: Mapped["Regulation | None"] = relationship()  # noqa: F821
