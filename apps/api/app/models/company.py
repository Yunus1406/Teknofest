"""Firma Gerçek Veri Kütüphanesi'nin kökü: Company -> Facility. MVP tek
kiracılıdır (tek Company + tek Facility seed edilir), ama makine/hammadde/
reçete gibi tüm firma-katmanı varlıklar buraya FK ile bağlanarak sistem
referans kütüphanesinden (Polymer, Regulation, CarbonEmissionFactor —
company_id TAŞIMAZ) şema düzeyinde ayrışır. Çok kiracılı bir geleceğe
geçildiğinde bu FK'ler doğrudan filtre olarak kullanılabilir hale gelir.

Faz E.1 — Firma Profili: boolean E/H alanları (`exports_to_eu`,
`produces_food_packaging`, `renewable_energy_used`) KASITLI olarak
`bool | None` — `None` = "Veri Girilmedi", ASLA `False`'a düşülmez (Faz
A/B'nin "EF TANIMLANMADI" disipliniyle aynı ilke: bilinmeyen ≠ hayır).
`logo_url` bir referans alanıdır — dosya yükleme altyapısı kurulmadı."""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class Company(Base, IdMixin, TimestampMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200))

    # --- Faz E.1: Firma Profili ---------------------------------------
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)  # ticari marka
    tax_country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    business_area: Mapped[str | None] = mapped_column(String(200), nullable=True)  # faaliyet alanı
    nace_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Bu iki alan, aşağıdaki Facility'lerin toplamından FARKLI bir kaynak
    # olabilir (ör. firma tescil belgesindeki kendi beyan ettiği rakam) —
    # bilinçli olarak facility toplamından TÜRETİLMEZ, ayrı saklanır.
    annual_production_capacity_tons: Mapped[float | None] = mapped_column(Float, nullable=True)
    annual_actual_production_tons: Mapped[float | None] = mapped_column(Float, nullable=True)
    main_export_markets: Mapped[list] = mapped_column(default=list)
    exports_to_eu: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    produces_food_packaging: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    facilities: Mapped[list["Facility"]] = relationship(back_populates="company")


class Facility(Base, IdMixin, TimestampMixin):
    __tablename__ = "facilities"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(400), nullable=True)

    # --- Faz E.1: Tesis Profili ----------------------------------------
    code: Mapped[str | None] = mapped_column(String(40), nullable=True)  # tesis kodu
    production_area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    annual_capacity_tons: Mapped[float | None] = mapped_column(Float, nullable=True)
    working_days_per_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shift_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    working_hours_per_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    main_processes: Mapped[list] = mapped_column(default=list)
    electricity_consumption_kwh_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    gas_consumption_m3_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    renewable_energy_used: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    renewable_energy_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    company: Mapped["Company"] = relationship(back_populates="facilities")


class CompanyBenchmark(Base, IdMixin, TimestampMixin):
    """Faz N.2 (Madde 15) — Faz F.11'in `BenchmarkReference`'ından (sistem-
    geneli, company_id YOK, kasıtlı boş -- uydurma sektör ortalaması ASLA
    üretilmez) TAMAMEN AYRI: bu, kullanıcının/firmanın KENDİ girdiği gerçek
    referans veridir (kendi geçmiş üretim ortalaması ya da doğrulanmış bir
    dış kaynak, ör. sektör raporu). `source` HANGİSİ olduğunu serbest
    metinle taşır -- sistem bunu asla otomatik üretmez/tahmin etmez.
    `packaging_category`/`metric_name` sabit, bilinen kümelerden (bkz.
    app/schemas/company.py COMPANY_BENCHMARK_METRICS ve app/services/
    common.py CANONICAL_PACKAGING_CATEGORIES) -- serbest metin DEĞİL, ki
    Aşama 12/Rapor'daki karşılaştırma GERÇEKTEN aynı büyüklüğü aynı
    büyüklükle kıyaslasın."""

    __tablename__ = "company_benchmarks"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    packaging_category: Mapped[str] = mapped_column(String(80))
    metric_name: Mapped[str] = mapped_column(String(40))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(300))
