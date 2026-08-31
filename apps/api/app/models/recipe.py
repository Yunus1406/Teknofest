"""Ambalaj talebi, mevzuat değerlendirmesi ve reçete (+versiyon soyu) modelleri."""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin
from app.models.enums import PackagingStatus


class PackagingRequest(Base, IdMixin, TimestampMixin):
    __tablename__ = "packaging_requests"

    packaging_type: Mapped[str] = mapped_column(String(120))  # örn. "plastik tabak"
    usage_area: Mapped[str] = mapped_column(String(160))
    product: Mapped[str] = mapped_column(String(160))
    target_market: Mapped[str] = mapped_column(String(120))
    food_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    target_volume_units: Mapped[int] = mapped_column(Integer, default=0)
    dimensions: Mapped[dict] = mapped_column(default=dict)  # {"length_mm":..,"width_mm":..}

    spec_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extracted_fields: Mapped[dict] = mapped_column(default=dict)
    # LLM tabanlı şartname çıkarımının çıktısı + kullanıcı tarafından düzeltilen alanlar

    status: Mapped[str] = mapped_column(String(30), default=PackagingStatus.DRAFT.value)

    sku_id: Mapped[str | None] = mapped_column(ForeignKey("product_skus.id"), nullable=True)
    # Bu case hangi kalıcı Ürün/SKU'yu hedefliyor (bkz. app/models/product_sku.py).
    # None ise tek seferlik/deneysel bir talep — SKU'ya bağlı değil.

    regulatory_assessments: Mapped[list["RegulatoryAssessment"]] = relationship(
        back_populates="packaging_request"
    )
    recipes: Mapped[list["Recipe"]] = relationship(back_populates="packaging_request")
    sku = relationship("ProductSku", back_populates="packaging_requests")


class RegulatoryAssessment(Base, IdMixin, TimestampMixin):
    __tablename__ = "regulatory_assessments"

    packaging_request_id: Mapped[str] = mapped_column(ForeignKey("packaging_requests.id"))
    regulation_id: Mapped[str] = mapped_column(ForeignKey("regulations.id"))
    verdict: Mapped[str] = mapped_column(String(30))  # RegulatoryVerdict
    reasoning: Mapped[str] = mapped_column(String(1000))

    packaging_request: Mapped["PackagingRequest"] = relationship(
        back_populates="regulatory_assessments"
    )
    regulation = relationship("Regulation")


class Recipe(Base, IdMixin, TimestampMixin):
    __tablename__ = "recipes"

    packaging_request_id: Mapped[str] = mapped_column(ForeignKey("packaging_requests.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_recipe_id: Mapped[str | None] = mapped_column(
        ForeignKey("recipes.id"), nullable=True
    )
    line_id: Mapped[str | None] = mapped_column(ForeignKey("production_lines.id"), nullable=True)

    source: Mapped[str] = mapped_column(String(30))  # RecipeSource
    status: Mapped[str] = mapped_column(String(30), default="taslak")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # doğrulanmış reçete firma hafızasına kaydedildiğinde True (aşama 12)

    total_gsm: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_micron: Mapped[float | None] = mapped_column(Float, nullable=True)

    packaging_request: Mapped["PackagingRequest"] = relationship(back_populates="recipes")
    layers: Mapped[list["RecipeLayer"]] = relationship(
        back_populates="recipe", order_by="RecipeLayer.layer_index", cascade="all, delete-orphan"
    )
    additives: Mapped[list["RecipeAdditive"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
    evaluations: Mapped[list["RecipeEvaluation"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["RecipeMetric"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )
    parent: Mapped["Recipe | None"] = relationship(remote_side="Recipe.id")


class RecipeLayer(Base, IdMixin):
    __tablename__ = "recipe_layers"

    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"))
    layer_index: Mapped[int] = mapped_column(Integer)  # 0 = en dış katman
    layer_label: Mapped[str] = mapped_column(String(10))  # "A", "B", "C"...
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"))
    ratio_pct: Mapped[float] = mapped_column(Float)  # katman içindeki bu malzemenin oranı
    thickness_micron: Mapped[float] = mapped_column(Float)

    recipe: Mapped["Recipe"] = relationship(back_populates="layers")
    material = relationship("Material")


class RecipeAdditive(Base, IdMixin):
    __tablename__ = "recipe_additives"

    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"))
    additive_id: Mapped[str] = mapped_column(ForeignKey("additives.id"))
    dosage_pct: Mapped[float] = mapped_column(Float)
    layer_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Hangi katmanda kullanıldığı (bkz. RecipeLayer.layer_index) — Faz B.3
    # katman bazlı gösterim için. NULL: katman bilgisi yok/tüm reçeteye genel
    # (ör. eski kayıtlar). Aday üretimi (candidate_generator.py) şu an hiç
    # additive atamıyor -- bu alan görüntüleme/ileri genişletme için hazır.

    recipe: Mapped["Recipe"] = relationship(back_populates="additives")
    additive = relationship("Additive")


class RecipeEvaluation(Base, IdMixin, TimestampMixin):
    """Kısıt motoru + optimizasyonun bir aday reçete için ürettiği tekil
    değerlendirme kaydı. Hiç üzerine yazılmaz (append-only) — reçete geçmişi
    ve ileride ML eğitim verisi için."""

    __tablename__ = "recipe_evaluations"

    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"))
    tier: Mapped[str] = mapped_column(String(40))  # EvaluationTier
    verdict: Mapped[str] = mapped_column(String(20))  # EvaluationVerdict
    reason_code: Mapped[str] = mapped_column(String(80))
    reason_text: Mapped[str] = mapped_column(String(1000))
    data_confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)  # DataConfidence

    recipe: Mapped["Recipe"] = relationship(back_populates="evaluations")


class RecipeMetric(Base, IdMixin, TimestampMixin):
    __tablename__ = "recipe_metrics"

    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"))
    metric_type: Mapped[str] = mapped_column(String(40))  # MetricType
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))
    is_estimated: Mapped[bool] = mapped_column(Boolean, default=True)
    data_source_type: Mapped[str] = mapped_column(String(40))  # DataSourceType

    recipe: Mapped["Recipe"] = relationship(back_populates="metrics")
