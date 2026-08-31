"""Bilgi Tabanı: polimer türleri, virgin/PCR/PIR-regranül hammaddeler, katkı
maddeleri, karbon emisyon faktörü kütüphanesi ve PPWR'nin kritik maddeleri.
Yapılandırılmış, sorgulanabilir veri.

Material -> PcrMaterial / PirMaterial single-table inheritance (STI) ile
modellenir: aynı fiziksel `materials` tablosu, ama PCR ve PIR birbirinden
TAMAMEN AYRI Python sınıfları ve kendi alan setleri ile temsil edilir (bkz.
Faz B.2). `RecipeLayer.material_id` tek bir `materials.id` FK olarak kalır;
polymorphic sorgu şeffaf çalışır — `recipe_layer.material` her zaman doğru
alt sınıfın (Material/PcrMaterial/PirMaterial) örneğini döner."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class Polymer(Base, IdMixin, TimestampMixin):
    __tablename__ = "polymers"

    code: Mapped[str] = mapped_column(String(20), unique=True)  # PE, PP, PET, PLA...
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(60))  # poliolefin, polyester, biyopolimer...
    base_properties: Mapped[dict] = mapped_column(default=dict)
    # örn: {"density_g_cm3": 0.92, "melt_temp_c": 130, "food_contact_eligible": true}

    materials: Mapped[list["Material"]] = relationship(back_populates="polymer")


class CarbonEmissionFactor(Base, IdMixin, TimestampMixin):
    """Karbon Veri Kütüphanesi (Sistem Referans — company_id taşımaz, EF'ler
    tipik olarak LCA veritabanlarından/EPD'lerden gelir, firmaya özel değildir).

    ÖNEMLİ: Bu sistemde şu an gerçek/kaynaklı bir EF veritabanı entegrasyonu
    YOK. Seed edilen tüm satırlar `is_demo_placeholder=True` ve
    `source="DEMO/VARSAYIMSAL — kaynak yok"` taşır — bu durum UI'da her karbon
    gösteriminde açıkça etiketlenir (bkz. app/services/carbon.py). Bir
    malzemenin `carbon_ef_id`'si hiç set değilse (None), o malzeme için EF
    "TANIMLANMADI" kabul edilir — asla sessizce 0 ya da uydurma bir sayıya
    düşülmez (görüntüleme amacıyla; iç skorlama en kötü ihtimalle 0'a düşer,
    ama durum etiketi dürüstçe 'tanımlanmadı' kalır)."""

    __tablename__ = "carbon_emission_factors"

    material_key: Mapped[str] = mapped_column(String(160))
    # okunabilirlik için tanımlayıcı etiket (ör. "PP Virgin") — bağlayıcı olan
    # Material.carbon_ef_id FK'sidir, bu alan sadece EF kütüphanesi tablosunu
    # tek başına anlamlı kılmak için.
    ef_value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40), default="kg_co2e_per_kg")
    source: Mapped[str] = mapped_column(String(300))
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    geography: Mapped[str | None] = mapped_column(String(80), nullable=True)
    version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_demo_placeholder: Mapped[bool] = mapped_column(Boolean, default=True)

    materials: Mapped[list["Material"]] = relationship(back_populates="carbon_ef")


class Material(Base, IdMixin, TimestampMixin):
    """Hammadde Teknik Kartı (Firma Gerçek Veri Kütüphanesi). Taban sınıf =
    Virgin; `PcrMaterial`/`PirMaterial` polymorphic alt sınıflardır (bkz.
    modül docstring'i)."""

    __tablename__ = "materials"

    polymer_id: Mapped[str] = mapped_column(ForeignKey("polymers.id"))
    name: Mapped[str] = mapped_column(String(160))
    material_type: Mapped[str] = mapped_column(String(20))  # ayrımcı: virgin/pcr/regranul (=PIR)
    source: Mapped[str | None] = mapped_column(String(160), nullable=True)  # tedarikçi/kaynak (serbest metin)

    # --- Genel hammadde teknik kartı alanları (virgin/PCR/PIR ortak) -------
    manufacturer: Mapped[str | None] = mapped_column(String(160), nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(160), nullable=True)
    color: Mapped[str | None] = mapped_column(String(60), nullable=True)
    certification_status: Mapped[str | None] = mapped_column(String(200), nullable=True)
    suitable_layer_position: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # ör. "sadece_cekirdek", "her_katman", "temas_katmani_haric"

    mfi_g_10min: Mapped[float | None] = mapped_column(Float, nullable=True)
    density_g_cm3: Mapped[float | None] = mapped_column(Float, nullable=True)
    degradation_factor: Mapped[float] = mapped_column(Float, default=0.0)
    # regranül/PCR devir sayısına bağlı mekanik kayıp katsayısı (0=kayıpsız)
    tensile_strength_mpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    elongation_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    dart_impact_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    melt_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    processing_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    additive_content_note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    food_contact_eligible: Mapped[bool] = mapped_column(default=True)
    max_recommended_ratio_pct: Mapped[float] = mapped_column(Float, default=100.0)
    # bu malzemenin bir katmanda güvenle kullanılabileceği azami oran

    cost_per_kg: Mapped[float] = mapped_column(Float, default=0.0)
    # Faz A/1'den kalan, doğrudan sayısal karbon faktörü. carbon_ef_id
    # bağlıysa artık İKİNCİL kaynak sayılır (bkz. app/services/carbon.py);
    # geriye dönük uyumluluk + carbon_ef bağlı olmayan kayıtlarda iç skorlama
    # arithmetiğinin çökmemesi için tutulur.
    carbon_factor_kg_co2_per_kg: Mapped[float] = mapped_column(Float, default=0.0)
    carbon_ef_id: Mapped[str | None] = mapped_column(
        ForeignKey("carbon_emission_factors.id"), nullable=True
    )

    stock_qty_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    lot_number: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # --- Faz E.3: Hammadde Kütüphanesi genişlemesi ----------------------
    currency: Mapped[str] = mapped_column(String(10), default="TRY")  # cost_per_kg'ın para birimi
    origin_country: Mapped[str | None] = mapped_column(String(80), nullable=True)  # menşe
    technical_datasheet_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    compliance_documents_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # `certification_status` bir DURUM metnidir (ör. "Gıda sınıfı sertifikalı");
    # bu ise o sertifikanın/belgenin KENDİSİNE bir referans (dosya/link/no).

    properties: Mapped[dict] = mapped_column(default=dict)

    polymer: Mapped["Polymer"] = relationship(back_populates="materials")
    carbon_ef: Mapped["CarbonEmissionFactor | None"] = relationship(back_populates="materials")

    __mapper_args__ = {
        "polymorphic_on": "material_type",
        "polymorphic_identity": "virgin",
    }


class PcrMaterial(Material):
    """PCR (Post-Consumer Recycled) Kütüphanesi — Virgin'den ve PIR'dan
    TAMAMEN AYRI bir hammadde sınıfı. PPWR Md.7'nin geri dönüştürülmüş içerik
    hesabına giren TEK kategori budur (bkz. app/optimization/scorer.py
    `_regulatory_margin_score` — yalnızca material_type='pcr' sayılır)."""

    __mapper_args__ = {"polymorphic_identity": "pcr"}

    contamination_level: Mapped[str | None] = mapped_column(String(60), nullable=True)
    odor_level: Mapped[str | None] = mapped_column(String(60), nullable=True)
    technical_constraints: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # Faz E.3 — bu PCR malzemesinin GERÇEKTEN ne kadarı post-consumer
    # kaynaklı (bir PCR hammaddesi %100 saf olmayabilir, karışım olabilir).
    # SADECE PcrMaterial'da vardır — PirMaterial'a (pre-consumer/internal)
    # ASLA sızmaz (STI ayrımı, bkz. modül docstring'i).
    post_consumer_content_pct: Mapped[float | None] = mapped_column(Float, nullable=True)


class PirMaterial(Material):
    """PIR/Regranül (Pre-Consumer/Internal) Kütüphanesi — PCR ile ASLA aynı
    sınıfa yazılmaz. Kaynak proses + kaynak makine/reçete izlenebilirliği
    taşır (Firma Hafızası Zinciri'nin bir parçası). Veritabanı düzeyinde
    ayrımcı değeri tarihsel nedenlerle hâlâ 'regranul' (bkz. MaterialType
    enum) — PIR terimiyle eşanlamlıdır, UI'da 'PIR-Regranül' olarak gösterilir."""

    __mapper_args__ = {"polymorphic_identity": "regranul"}

    source_process: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # ör. "Film Ekstrüzyon Kenar Fire Geri Kazanımı"
    production_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_machine_id: Mapped[str | None] = mapped_column(
        ForeignKey("production_lines.id"), nullable=True
    )
    source_recipe_id: Mapped[str | None] = mapped_column(ForeignKey("recipes.id"), nullable=True)


class Additive(Base, IdMixin, TimestampMixin):
    """Masterbatch ve Katkılar Kütüphanesi (Firma Gerçek Veri Kütüphanesi)."""

    __tablename__ = "additives"

    name: Mapped[str] = mapped_column(String(160))
    additive_type: Mapped[str] = mapped_column(String(60))  # masterbatch, stabilizatör, kayganlaştırıcı...
    manufacturer: Mapped[str | None] = mapped_column(String(160), nullable=True)
    carrier_polymer: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # taşıyıcı reçine (ör. "PP", "PE") — hangi polimer ailesiyle uyumlu olduğunu belirtir
    regulatory_document_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # ör. "EU 10/2011 Uygunluk Beyanı Mevcut" — mevzuat belgesi referansı
    effects: Mapped[dict] = mapped_column(default=dict)
    # örn: {"uv_stabilizasyon": true, "mekanik_etki": "notr"}
    dosage_min_pct: Mapped[float] = mapped_column(Float, default=0.0)
    dosage_max_pct: Mapped[float] = mapped_column(Float, default=2.0)
    food_contact_eligible: Mapped[bool] = mapped_column(default=True)
    cost_per_kg: Mapped[float] = mapped_column(Float, default=0.0)
    carbon_ef_id: Mapped[str | None] = mapped_column(
        ForeignKey("carbon_emission_factors.id"), nullable=True
    )
    # bkz. app/services/carbon.py — EF bağlı değilse "EF TANIMLANMADI".

    carbon_ef: Mapped["CarbonEmissionFactor | None"] = relationship()


class Regulation(Base, IdMixin, TimestampMixin):
    __tablename__ = "regulations"

    code: Mapped[str] = mapped_column(String(40), unique=True)  # örn. PPWR-ART6
    title: Mapped[str] = mapped_column(String(240))
    category: Mapped[str] = mapped_column(String(60))
    # ambalaj_minimizasyonu, geri_donusturulebilirlik, geri_donusturulmus_icerik, gida_temasi
    description: Mapped[str] = mapped_column(String(2000))
    criteria: Mapped[dict] = mapped_column(default=dict)
    # örn: {"min_pcr_content_pct": 30, "applies_from": "2030-01-01"}
    applicable_packaging_types: Mapped[list] = mapped_column(default=list)
