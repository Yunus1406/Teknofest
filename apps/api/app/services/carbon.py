"""Karbon Emisyon Faktörü (EF) durum çözümleme.

Tek bir yerden yönetilir ki `optimization/scorer.py`, `mass_balance.py` ve
`dashboard_aggregation.py` aynı mantığı tekrarlamasın ve tutarsızlaşmasın.

Üç durum:
  - TANIMLANMADI: Material.carbon_ef_id hiç set değil — hiçbir kaynak yok.
  - TANIMLI_DEMO: bir CarbonEmissionFactor bağlı ama is_demo_placeholder=True
    (bu sistemde şu an TÜM seed EF'leri bu durumda — gerçek bir LCA
    veritabanı entegrasyonu yok).
  - TANIMLI_GERCEK: bağlı EF gerçek/kaynaklı (is_demo_placeholder=False).

`resolve_carbon_ef`, `.carbon_ef` ilişkisi hiç var olmayan (ör. eski test
mock'ları) nesnelerde de güvenle çalışsın diye `getattr(..., None)` kullanır."""

TANIMLANMADI = "tanimlanmadi"
TANIMLI_DEMO = "tanimli_demo"
TANIMLI_GERCEK = "tanimli_gercek"

_STATUS_PRIORITY = {TANIMLANMADI: 0, TANIMLI_DEMO: 1, TANIMLI_GERCEK: 2}  # düşük = daha az güvenilir

_STATUS_LABELS = {
    TANIMLANMADI: "EF TANIMLANMADI",
    TANIMLI_DEMO: "DEMO / VARSAYIMSAL EF",
    TANIMLI_GERCEK: "Kaynaklı EF",
}


def resolve_carbon_ef(material) -> tuple[float, str, str | None]:
    """(kg_co2_per_kg, durum, kaynak) döner.

    EF bağlı değilse iç skorlama arithmetiği çökmesin diye legacy
    `carbon_factor_kg_co2_per_kg` sütununa (varsa) düşer — ama durum
    dürüstçe TANIMLANMADI kalır; hiçbir zaman bu sessiz düşüşü 'kaynaklı EF'
    gibi göstermez."""
    ef = getattr(material, "carbon_ef", None)
    if ef is None:
        legacy = getattr(material, "carbon_factor_kg_co2_per_kg", None) or 0.0
        return legacy, TANIMLANMADI, None
    status = TANIMLI_DEMO if ef.is_demo_placeholder else TANIMLI_GERCEK
    return ef.ef_value, status, ef.source


def worst_status(statuses: list[str]) -> str:
    """Birden fazla malzemenin/katmanın durumları arasından en az güvenilir
    olanı seçer — bir reçetede TEK bir tanımsız/demo EF varsa, tüm reçetenin
    karbon figürü o düşük güven seviyesini yansıtmalı."""
    if not statuses:
        return TANIMLANMADI
    return min(statuses, key=lambda s: _STATUS_PRIORITY.get(s, 0))


def status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status)
