"""Faz I.3 — Gerçek Öğrenme Hafızası. Bkz. app/services/learning_memory_service.py."""
from datetime import datetime

from pydantic import BaseModel


class CausalChainNodeOut(BaseModel):
    id: str
    version: int
    status: str
    is_verified: bool
    created_at: datetime
    # Bir önceki versiyona göre GERÇEK kompozisyon farkı; kök versiyon (ilk
    # halka) için None -- karşılaştırılacak bir önceki yok.
    diff_from_previous: list[dict] | None = None
    line_name: str | None = None
    target_process_parameters: list[dict] = []
    # Üretim/canlı veri yoksa None -- uydurulmaz.
    gerceklesen_fire_kg: float | None = None
    gerceklesen_enerji_kwh: float | None = None
    physical_test_summary: dict


class ChangeOutcomeStatsOut(BaseModel):
    # {"degisiklik_yok": {"basarili": N, "revizyon_gerekti": N, "beklemede": N}, ...}
    buckets: dict[str, dict[str, int]]
