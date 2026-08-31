"""Faz F.12 — Merkezi Veri Çözümleme Servisi.

Sistemde bir değer gerektiğinde (karbon faktörü, test kabul aralığı, maliyet
kalemi...) hangi kaynaktan geleceğini TEK bir yerde, tutarlı bir öncelik
sırasıyla belirler. Var olan tekil-amaçlı çözümleyicilere (ör.
app/services/carbon.py'nin resolve_carbon_ef'i, kendi 3 durumlu -- tanimlanmadi/
tanimli_demo/tanimli_gercek -- deseniyle zaten doğru çalışıyor) DOKUNMAZ; bu
servis SADECE Faz F'te eklenen YENİ karar noktaları (F.6 mekanik test önerisi,
F.10 maliyet referansı gibi) için kullanılır, ileride yeni veri türleri
eklenince aynı hiyerarşiye otomatik uysun diye.

Öncelik sırası (1 en güvenilir, 7 en az güvenilir):
  1. FIRMA_OLCUM     -- firmanın kendi laboratuvar/ölçüm sonucu (Faz A/D)
  2. FIRMA_URETIM    -- firmanın kendi makine/üretim verisi (Faz B)
  3. FIRMA_HAFIZA    -- firmanın geçmiş doğrulanmış reçete/hafıza verisi (Faz B.9)
  4. TEDARIKCI_FOYU  -- tedarikçi teknik veri föyü (Faz E hammadde kartı)
  5. MEVZUAT         -- mevzuat kaynaklı değer (Faz B/F mevzuat kütüphanesi)
  6. SISTEM_REFERANS -- sistem referans kütüphanesi (bu fazda kurulan F.1-F.11)
  7. VARSAYIM        -- varsayım/tahmin (SADECE "DEMO/VARSAYIMSAL" etiketiyle)

Bir adayın değeri `None` ise o seviye "boş" sayılır ve bir sonraki (daha az
güvenilir) seviyeye geçilir -- hiçbir zaman sessizce 0 ya da uydurma bir
sayıya düşülmez; hiçbir seviye dolu değilse `resolve_value` `None` döner."""
from dataclasses import dataclass
from enum import Enum


class SourceTier(Enum):
    FIRMA_OLCUM = "firma_olcum"
    FIRMA_URETIM = "firma_uretim"
    FIRMA_HAFIZA = "firma_hafiza"
    TEDARIKCI_FOYU = "tedarikci_foyu"
    MEVZUAT = "mevzuat"
    SISTEM_REFERANS = "sistem_referans"
    VARSAYIM = "varsayim"


_PRIORITY: dict[SourceTier, int] = {
    SourceTier.FIRMA_OLCUM: 1,
    SourceTier.FIRMA_URETIM: 2,
    SourceTier.FIRMA_HAFIZA: 3,
    SourceTier.TEDARIKCI_FOYU: 4,
    SourceTier.MEVZUAT: 5,
    SourceTier.SISTEM_REFERANS: 6,
    SourceTier.VARSAYIM: 7,
}

_TIER_LABELS: dict[SourceTier, str] = {
    SourceTier.FIRMA_OLCUM: "Firma Ölçümü",
    SourceTier.FIRMA_URETIM: "Firma Üretim Verisi",
    SourceTier.FIRMA_HAFIZA: "Firma Hafızası",
    SourceTier.TEDARIKCI_FOYU: "Tedarikçi Veri Föyü",
    SourceTier.MEVZUAT: "Mevzuat",
    SourceTier.SISTEM_REFERANS: "Sistem Referans Kütüphanesi",
    SourceTier.VARSAYIM: "Varsayım/Tahmin",
}


@dataclass(frozen=True)
class Candidate:
    tier: SourceTier
    value: float | None
    unit: str | None = None
    source_text: str | None = None
    year: int | None = None
    version: str | None = None
    is_demo_placeholder: bool = False


@dataclass(frozen=True)
class ResolvedValue:
    value: float
    tier: SourceTier
    tier_label: str
    unit: str | None = None
    source_text: str | None = None
    year: int | None = None
    version: str | None = None
    is_demo_placeholder: bool = False


def resolve_value(candidates: list[Candidate]) -> ResolvedValue | None:
    """Adayları önceliğe göre gezip değeri OLAN en güvenilir adayı döner.
    `candidates` sırasız gelebilir -- sıralama burada, tier önceliğine göre
    yapılır. Hiçbir adayın değeri yoksa (hepsi None) `None` döner -- asla
    varsayılan bir sayıya düşülmez."""
    usable = [c for c in candidates if c.value is not None]
    if not usable:
        return None
    best = min(usable, key=lambda c: _PRIORITY[c.tier])
    return ResolvedValue(
        value=best.value,
        tier=best.tier,
        tier_label=_TIER_LABELS[best.tier],
        unit=best.unit,
        source_text=best.source_text,
        year=best.year,
        version=best.version,
        is_demo_placeholder=best.is_demo_placeholder,
    )


def tier_label(tier: SourceTier) -> str:
    return _TIER_LABELS[tier]
