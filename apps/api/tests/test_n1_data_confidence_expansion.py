"""Faz N.1a (Madde 14) — Faz G.4'ün 5 kademeli firma hafızası tier'ları
(ayni_sku/ayni_ambalaj_turu/benzer_kullanim_alani/benzer_teknik_sartlar/
ayni_hat) artık `report_service.data_confidence_level()`'in tanıdığı
kaynaklar arasında -- kademe SIRASI güven sırasına karşılık gelir."""
from app.services.report_service import data_confidence_level


def test_tier_1_2_map_to_yuksek():
    assert data_confidence_level("ayni_sku") == "Yüksek"
    assert data_confidence_level("ayni_ambalaj_turu") == "Yüksek"


def test_tier_3_4_map_to_orta():
    assert data_confidence_level("benzer_kullanim_alani") == "Orta"
    assert data_confidence_level("benzer_teknik_sartlar") == "Orta"


def test_tier_5_maps_to_dusuk():
    assert data_confidence_level("ayni_hat") == "Düşük"


def test_unknown_tier_returns_none():
    assert data_confidence_level("bilinmeyen_kademe") is None


def test_existing_confidence_kinds_unaffected():
    """Regresyon kilidi: yeni 5 anahtar eklenirken mevcut değerler değişmemeli."""
    assert data_confidence_level("makineden_alinan") == "Yüksek"
    assert data_confidence_level("hesaplanan") == "Orta"
    assert data_confidence_level("mevzuat") == "Düşük"
    assert data_confidence_level("varsayimsal") == "Varsayımsal"
