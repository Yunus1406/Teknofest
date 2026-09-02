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
    # Faz Q.0/Q.2 (Madde 24) — additive. "basarili" | "basarisiz" | "beklemede".
    outcome: str
    basarisizlik_nedeni: str | None = None


class ChangeOutcomeStatsOut(BaseModel):
    # {"degisiklik_yok": {"basarili": N, "revizyon_gerekti": N, "beklemede": N}, ...}
    buckets: dict[str, dict[str, int]]


# Faz R.1 (Madde 26) — Ambalaj Yaşam Döngüsü Zaman Çizelgesi (bkz.
# app/services/lifecycle_service.py). `event_type`: sartname_olusturuldu |
# optimizasyon_calistirildi | recete_uretildi | recete_revize_edildi |
# pilot_uretim | fiziksel_test | uretime_serbest_birakildi |
# mevzuat_guncellendi.
class LifecycleEventOut(BaseModel):
    event_type: str
    baslik: str
    tarih: datetime
    detay: dict
