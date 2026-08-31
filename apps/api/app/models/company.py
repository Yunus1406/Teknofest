"""Firma Gerçek Veri Kütüphanesi'nin kökü: Company -> Facility. MVP tek
kiracılıdır (tek Company + tek Facility seed edilir), ama makine/hammadde/
reçete gibi tüm firma-katmanı varlıklar buraya FK ile bağlanarak sistem
referans kütüphanesinden (Polymer, Regulation, CarbonEmissionFactor —
company_id TAŞIMAZ) şema düzeyinde ayrışır. Çok kiracılı bir geleceğe
geçildiğinde bu FK'ler doğrudan filtre olarak kullanılabilir hale gelir."""
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class Company(Base, IdMixin, TimestampMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200))

    facilities: Mapped[list["Facility"]] = relationship(back_populates="company")


class Facility(Base, IdMixin, TimestampMixin):
    __tablename__ = "facilities"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(400), nullable=True)

    company: Mapped["Company"] = relationship(back_populates="facilities")
