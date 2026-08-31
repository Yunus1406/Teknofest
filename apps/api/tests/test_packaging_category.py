"""Serbest metin ambalaj türü -> kanonik kategori eşleştirmesi.
Türkçe ünsüz yumuşaması (tabak->tabağı, kapak->kapağı, kap->kabı) nedeniyle
çekimli ifadelerin yanlış kategoriye düşmediğini doğrular — bkz. Dashboard 4
'uygun hat bulunamadı' hatası (kök neden: 'şişe kapağı' yalnızca 'şişe' ile
eşleşip yanlışlıkla şişe hattına yönleniyordu)."""
from app.services.common import canonical_packaging_category

CASES = [
    ("plastik tabak", "plastik_tabak"),
    ("Plastik Tabak", "plastik_tabak"),
    ("yemek tabağı", "plastik_tabak"),
    ("tabak", "plastik_tabak"),
    ("plastik bardak", "plastik_bardak"),
    ("kahve bardağı", "plastik_bardak"),
    ("PET şişe", "sise"),
    ("içecek şişesi", "sise"),
    ("şişe kapağı", "kapak"),  # asıl bug: eskiden yanlışlıkla "sise" dönüyordu
    ("vidalı kapak", "kapak"),
    ("kapaklı kap", "kapak"),  # "kapak" tam kelime olarak geçtiği için önce eşleşir
    ("esnek film ambalaj", "esnek_film_ambalaj"),
    ("atıştırmalık poşeti", "esnek_film_ambalaj"),
    ("saklama kabı", "plastik_kap"),
    ("yoğurt kabı", "plastik_kap"),
]


def test_canonical_packaging_category_handles_turkish_inflection():
    for packaging_type, expected in CASES:
        assert canonical_packaging_category(packaging_type) == expected, packaging_type


def test_unmatched_free_text_falls_back_to_slugified_input():
    assert canonical_packaging_category("özel ambalaj türü") == "özel_ambalaj_türü"
