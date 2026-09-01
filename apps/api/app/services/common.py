"""packaging_service ve optimization_service arasında paylaşılan küçük
yardımcılar: serbest metin ambalaj türünü (Aşama 2'de kullanıcının yazdığı
herhangi bir ifade) hem kanonik bir kategoriye hem de tercih edilen polimer
sırasına indirger.

Tek bir kural listesinden türetilir ki iki fonksiyon birbirinden sapmasın.
Türkçe ünsüz yumuşaması (tabak→tabağı, kapak→kapağı, kap→kabı gibi k/p
yumuşamaları) yaygın çekim ekleriyle birlikte ayrıca anahtar kelime olarak
eklenmiştir — aksi halde "şişe kapağı" gibi çekimli bir ifade, sadece "şişe"
ile eşleşip yanlış hatta yönlendirebilir."""

# (anahtar kelime, kanonik kategori slug'ı, tercih edilen polimer sırası)
# "kapak"/"kapağ" gibi daha spesifik kalıplar, "kap" gibi daha genel olandan
# ÖNCE kontrol edilir — aksi halde "kapak" ifadesi yanlışlıkla "kap"
# kategorisine düşer.
_PACKAGING_KEYWORD_RULES: list[tuple[str, str, list[str]]] = [
    ("kapak", "kapak", ["PP", "PE"]),
    ("kapağ", "kapak", ["PP", "PE"]),
    ("tabak", "plastik_tabak", ["PP", "PET", "PS"]),
    ("tabağ", "plastik_tabak", ["PP", "PET", "PS"]),
    ("bardak", "plastik_bardak", ["PP", "PS", "PET"]),
    ("bardağ", "plastik_bardak", ["PP", "PS", "PET"]),
    # Faz K.6 (Madde 8) — "tepsi"/"termoform" bu tabloda hiç YOKTU, bu yüzden
    # PET/rPET termoform tepsi talepleri _DEFAULT_POLYMER_PREFERENCE'e
    # (PP önce) düşüyor, "PP Virgin Enjeksiyon Sınıfı" gibi uyumsuz bir
    # başlangıç hammaddesi seçilebiliyordu. Termoform tepsi/kap PET/rPET
    # ağırlıklıdır (gıda sınıfı berraklık/sıcaklık dayanımı için) -- PP ikinci
    # sırada, tamamen dışlanmıyor.
    ("tepsi", "plastik_tepsi", ["PET", "PP"]),
    ("tepsiğ", "plastik_tepsi", ["PET", "PP"]),
    ("termoform", "plastik_tepsi", ["PET", "PP"]),
    ("şişe", "sise", ["PET", "PE"]),
    ("sise", "sise", ["PET", "PE"]),
    ("film", "esnek_film_ambalaj", ["PE", "PP"]),
    ("poşet", "esnek_film_ambalaj", ["PE", "PP"]),
    ("torba", "esnek_film_ambalaj", ["PE", "PP"]),
    ("pouch", "esnek_film_ambalaj", ["PE", "PP"]),
    ("kabı", "plastik_kap", ["PP", "PET"]),
    ("kabın", "plastik_kap", ["PP", "PET"]),
    ("kap", "plastik_kap", ["PP", "PET"]),
    ("kutu", "plastik_kap", ["PP", "PET"]),
]
_DEFAULT_POLYMER_PREFERENCE = ["PP", "PE", "PET"]

# Faz N.2 (Madde 15) — sistemin tanıdığı 7 kanonik ambalaj kategorisi, TEK
# kaynaktan (yukarıdaki kural tablosu) türetilir; elle ayrı bir liste
# TUTULMAZ (aksi halde yeni bir kategori eklendiğinde biri unutulabilir).
CANONICAL_PACKAGING_CATEGORIES: list[str] = sorted({category for _, category, _ in _PACKAGING_KEYWORD_RULES})


def slugify(text: str) -> str:
    return text.strip().lower().replace(" ", "_").replace("ı", "i")


def canonical_packaging_category(packaging_type: str) -> str:
    """'Plastik Tabak', 'yemek tabağı', 'tabak' gibi serbest metin
    girdilerini tek bir kanonik kategori slug'ına indirger. Üretim hatları
    (bkz. seed_demo.py) ve mevzuat kayıtları (regulations.yaml) hep bu
    kanonik slug'ları kullanır. Hiçbir anahtar kelime eşleşmezse, kullanıcının
    girdiği metnin doğrudan slug'ına düşer — bu da bilgi tabanına o tam
    ifadeyle eşleşen özel bir hat eklenebilmesini sağlar."""
    lowered = packaging_type.strip().lower()
    for keyword, category, _ in _PACKAGING_KEYWORD_RULES:
        if keyword in lowered:
            return category
    return slugify(packaging_type)


def preferred_polymer_codes(packaging_type: str) -> list[str]:
    lowered = packaging_type.strip().lower()
    for keyword, _, prefs in _PACKAGING_KEYWORD_RULES:
        if keyword in lowered:
            return prefs
    return _DEFAULT_POLYMER_PREFERENCE


def find_pcr_target_category(criteria: dict, food_contact: bool, is_pet: bool) -> dict | None:
    """PPWR-ART-7'nin (Geri Dönüştürülmüş İçerik) `criteria.targets` tablosundan
    (bkz. regulations.yaml), verilen bağlama (gıda teması + PET olup olmadığı)
    uyan kategori kaydını döner: {"category":..., "by_year": {"2030": 10, "2040": 25}}.

    Kategori tabloda tanımlı değilse None döner — sabit bir yüzde ASLA
    varsayılmaz (ör. PET'in kendi hedefi henüz doğrulanıp tabloya
    eklenmediyse, çağıran taraf 'belirlenmedi' demeli, %30 gibi bir sayı
    UYDURMAMALI)."""
    for entry in criteria.get("targets", []):
        if entry.get("food_contact") == food_contact and entry.get("pet") == is_pet:
            return entry
    return None


def recipe_is_pet_dominant(polymer_codes: list[str]) -> bool:
    """Basitleştirme: kısıt motoru zaten uyumsuz çok-polimer yapılarını
    elediğinden (bkz. rule_ppwr_recyclability_multi_material), hayatta kalan
    adaylar pratikte tek polimer ailesindendir — ilk katmanın polimeri
    kategoriyi belirler."""
    return bool(polymer_codes) and polymer_codes[0] == "PET"
