"""Firma Altyapısı (Makine Parkı): kayıtlı üretim hatları, proses tipleri,
katman yapıları, hat-malzeme uyumu. Bu tablo Firma Gerçek Veri Kütüphanesi'ne
aittir (facility_id ile Company/Facility köküne bağlıdır) — Polymer/
Regulation gibi sistem referans tablolarının aksine, buradaki her satır
gerçekten firmanın sahip olduğu bir makineyi temsil eder.

Faz E.2 — Makine Parkı genişlemesi: yeni sayısal/E-H alanların HEPSİ
opsiyoneldir ("Veri Girilmedi" ilkesi, bkz. app/models/company.py). Aday
üretim motoru (app/optimization/candidate_generator.py) bu yeni alanları
OKUMAZ — sadece mevcut zorunlu alanlara (layer_structure, min/max_micron,
material_compatibility) bakar, bu yüzden yeni alanlar boş kalsa bile
optimizasyon akışı bozulmaz."""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class ProductionLine(Base, IdMixin, TimestampMixin):
    __tablename__ = "production_lines"

    facility_id: Mapped[str | None] = mapped_column(ForeignKey("facilities.id"), nullable=True)

    name: Mapped[str] = mapped_column(String(160))
    process_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Blown Film Extrusion, Cast Film, Thermoforming, Injection Molding...
    layer_structure: Mapped[str] = mapped_column(String(40))  # "A", "A/B/A", "A/B/C/B/A"...
    layer_count: Mapped[int] = mapped_column(default=1)
    extruder_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    min_micron: Mapped[float] = mapped_column(Float)
    max_micron: Mapped[float] = mapped_column(Float)
    min_gsm: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_gsm: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_dosage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_dosage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    line_speed_m_min: Mapped[float] = mapped_column(Float, default=0.0)
    supported_packaging_types: Mapped[list] = mapped_column(default=list)
    energy_kwh_per_kg: Mapped[float] = mapped_column(Float, default=0.0)
    active: Mapped[bool] = mapped_column(default=True)

    # Gerçek makine entegrasyonu bu fazda yok; alanlar gelecekteki PLC/OPC-UA/
    # Modbus TCP/API bağlantısı için tutulur, MVP'de hepsi False kalır.
    plc_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    opc_ua_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    modbus_tcp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    api_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Faz E.2: Makine Parkı teknik kartı -----------------------------
    manufacturer: Mapped[str | None] = mapped_column(String(160), nullable=True)
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    install_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nominal_capacity_kg_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_capacity_kg_year: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Mevcut tekil `line_speed_m_min` geriye dönük uyumluluk için korunur —
    # bu iki alan onun min/max aralığıdır, onu YENİDEN ADLANDIRMAZ.
    min_line_speed_m_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_line_speed_m_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    layer_structure_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Mono/ABA/ABC/ABCBA — `layer_structure` (ör. "A/B/A") ile aynı bilgiyi
    # taşır ama makine kataloğu/dropdown'ı için sabit bir etiket olarak.
    screw_diameter_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    ld_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    suitable_polymer_codes: Mapped[list] = mapped_column(default=list)
    # Makinenin GENEL teknik olarak işleyebildiği polimer aileleri —
    # `material_compatibility`den (spesifik ONAYLANMIŞ malzeme satırları)
    # farklı, daha geniş bir beyan.
    pcr_capable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    pir_capable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    max_pcr_technical_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_pir_technical_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    gravimetric_dosing_equipped: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    online_thickness_control: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    energy_metering_equipped: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    average_waste_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # `active: bool` basit filtreleme için korunur; bu daha ayrıntılı bir
    # durum etiketidir (ör. "aktif"/"bakimda"/"devre_disi").
    availability_status: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # --- Faz G.3: Aşama 4'ten "Kayıtlı Makineden Hat Oluştur" ------------
    # Bu satır, makine parkındaki BAŞKA ProductionLine satırlarının (her biri
    # tek bir fiziksel ünite/makine olarak da kaydedilebilir) bir araya
    # getirilmesiyle oluşturulmuşsa, o bileşenlerin id'lerini taşır. Yeni bir
    # Equipment/BOM tablosu KURULMADI (bkz. plan G.3 kararı) -- mevcut
    # ProductionLine hem tekil makineyi hem birleşik hattı temsil eder, bu
    # alan sadece "bu hat hangi kayıtlı satırlardan türetildi" izini tutar.
    # None/[] = bu satır bileşik değil, doğrudan tanımlandı.
    component_line_ids: Mapped[list | None] = mapped_column(nullable=True)

    material_compatibility: Mapped[list["LineMaterialCompatibility"]] = relationship(
        back_populates="line"
    )


class LineMaterialCompatibility(Base, IdMixin, TimestampMixin):
    __tablename__ = "line_material_compatibility"

    line_id: Mapped[str] = mapped_column(ForeignKey("production_lines.id"))
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"))
    max_ratio_pct: Mapped[float] = mapped_column(Float, default=100.0)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    line: Mapped["ProductionLine"] = relationship(back_populates="material_compatibility")
