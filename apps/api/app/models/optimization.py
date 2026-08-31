"""Optimizasyon koşuları ve aday reçeteler (Dashboard 6-7)."""
from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin


class OptimizationRun(Base, IdMixin, TimestampMixin):
    __tablename__ = "optimization_runs"

    packaging_request_id: Mapped[str] = mapped_column(ForeignKey("packaging_requests.id"))
    parameters: Mapped[dict] = mapped_column(default=dict)
    # örn: {"ratio_step_pct": 10, "candidate_count_generated": 48}

    # Faz C.4 — `run_optimization()`'ın zaten hesapladığı "en yakın ıskalayan"
    # elenen aday özetini (bkz. optimization_service._eliminated_summary)
    # kalıcı hale getirir. Öncesinde bu veri sadece o anki API yanıtında
    # vardı, koşu bittikten sonra kayboluyordu — Rapor §6 ("Neden Elendi?")
    # bunu bir OptimizationRun'a geri dönüp okuyamıyordu. Eski satırlarda
    # (bu sütun eklenmeden önce) boş liste ile güvenle okunur (bkz.
    # migration'daki server_default).
    notable_eliminated: Mapped[list] = mapped_column(default=list)

    candidates: Mapped[list["OptimizationCandidate"]] = relationship(back_populates="run")


class OptimizationCandidate(Base, IdMixin, TimestampMixin):
    __tablename__ = "optimization_candidates"

    run_id: Mapped[str] = mapped_column(ForeignKey("optimization_runs.id"))
    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"))

    score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    is_finalist: Mapped[bool] = mapped_column(default=False)  # sunulan 3-4 alternatiften biri mi

    score_breakdown: Mapped[dict] = mapped_column(default=dict)
    # örn: {"teknik_performans": 0.7, "uretilebilirlik": 0.9, "mevzuat_marji": 1.0, ...}
    carbon_data_quality: Mapped[str] = mapped_column(String(20), default="tanimlanmadi")
    # bkz. app/services/carbon.py -- "tanimli_gercek"/"tanimli_demo"/"tanimlanmadi";
    # Dashboard 6/7/8'de "DEMO/VARSAYIMSAL EF" ya da "EF TANIMLANMADI" rozeti için.

    justification_text: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    decision_basis: Mapped[dict] = mapped_column(default=dict)
    # "Karar Dayanağı": {"gecmis_receteler": [...], "mevzuat_maddeleri": [...], "hat_parametreleri": {...}}

    run: Mapped["OptimizationRun"] = relationship(back_populates="candidates")
    recipe = relationship("Recipe")
