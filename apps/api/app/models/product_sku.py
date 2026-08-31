"""Ürün/SKU Kütüphanesi (Firma Gerçek Veri Kütüphanesi) — bir firmanın
GERÇEKTEN ÜRETTİĞİ/ürettiği ürünün kalıcı kimliği. `PackagingRequest`
(Aşama 2'deki tekil "case") bundan farklıdır: bir SKU zaman içinde birden
fazla PackagingRequest/optimizasyon turundan geçebilir (V1, V2, revizyon...),
`current_recipe_id` her zaman o SKU için o an geçerli DOĞRULANMIŞ reçeteyi
gösterir. Bu, `find_reference_recipe`'in salt metin eşleşmesinden
(packaging_type) daha kesin bir referans bulma yolu sunar (bkz.
app/services/packaging_service.py)."""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class ProductSku(Base, IdMixin, TimestampMixin):
    __tablename__ = "product_skus"

    sku_code: Mapped[str] = mapped_column(String(60), unique=True)
    product_name: Mapped[str] = mapped_column(String(200))
    packaging_type: Mapped[str] = mapped_column(String(120))
    usage_area: Mapped[str] = mapped_column(String(160))
    customer: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # Faz E.4 — `customer` bir MÜŞTERİ ADIdır; bu ise o müşterinin ait olduğu
    # SEKTÖR (ör. "gıda", "kozmetik", "kimya") — ayrı ve tamamlayıcı bir alan.
    customer_sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_market: Mapped[str] = mapped_column(String(120))
    food_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    dimensions: Mapped[dict] = mapped_column(default=dict)
    film_thickness_micron: Mapped[float | None] = mapped_column(Float, nullable=True)
    gsm: Mapped[float | None] = mapped_column(Float, nullable=True)
    layer_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    layer_structure: Mapped[str | None] = mapped_column(String(40), nullable=True)

    line_id: Mapped[str | None] = mapped_column(ForeignKey("production_lines.id"), nullable=True)
    # use_alter=True: product_skus -> recipes -> packaging_requests -> product_skus
    # ÇEMBERSEL bir FK zinciri oluşturuyor (SKU bir reçeteye, reçete bir talebe,
    # talep de SKU'ya işaret edebiliyor). SQLAlchemy/Alembic tablo oluşturma
    # sırasını bu döngüde çözemiyor; use_alter bu TEK constraint'i tüm tablolar
    # oluşturulduktan SONRA ayrı bir ALTER TABLE ile eklenmeye zorlar.
    current_recipe_id: Mapped[str | None] = mapped_column(
        ForeignKey("recipes.id", use_alter=True, name="fk_product_skus_current_recipe_id"),
        nullable=True,
    )
    # SKU'nun o an geçerli DOĞRULANMIŞ reçetesi — bkz. production_flow_service.py
    # finalize_result: bir reçete doğrulandığında (Aşama 12) ve bu SKU'ya
    # bağlıysa otomatik güncellenir.

    technical_spec_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    physical_test_criteria: Mapped[dict] = mapped_column(default=dict)

    packaging_requests: Mapped[list["PackagingRequest"]] = relationship(back_populates="sku")
