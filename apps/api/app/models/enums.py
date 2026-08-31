from enum import StrEnum


class MaterialType(StrEnum):
    VIRGIN = "virgin"
    PCR = "pcr"
    REGRANULE = "regranul"


class PackagingStatus(StrEnum):
    DRAFT = "taslak"
    ASSESSED = "degerlendirildi"
    MATCHED = "eslesme_tamam"
    RECIPE_READY = "recete_hazir"


class RegulatoryVerdict(StrEnum):
    OK = "uygun_gorunuyor"
    REVIEW = "inceleme_gerekli"
    NOT_OK = "uygun_degil"
    # Faz G.2 — eskiden bu iki durum da REVIEW'e düşüyordu; ayrıştırılınca
    # "kullanıcı karar vermeli" (REVIEW) ile "sistemin eksik verisi var"
    # (MISSING_DATA) ve "bu madde otomatik doğrulanamaz, insan/lab gerekir"
    # (NO_METHODOLOGY) birbirinden ayrışır -- ikisi de bir "onay/red" iddiası
    # DEĞİLDİR, bkz. app/services/packaging_service.py.
    MISSING_DATA = "veri_eksik"
    NO_METHODOLOGY = "henuz_metodoloji_yok"


class EvaluationTier(StrEnum):
    KESIN_TEKNIK_KISIT = "kesin_teknik_kisit"
    MALZEME_PROSES_KISITI = "malzeme_proses_kisiti"
    TAHMINI_FIZIKSEL_PERFORMANS = "tahmini_fiziksel_performans"


class EvaluationVerdict(StrEnum):
    ELENDI = "elendi"
    GECTI = "gecti"


class DataConfidence(StrEnum):
    YUKSEK = "yuksek"
    ORTA = "orta"
    DUSUK = "dusuk"


class DataSourceType(StrEnum):
    HESAPLANAN = "hesaplanan"
    GECMIS_URETIM_VERISI = "gecmis_uretim_verisi"
    MAKINEDEN_ALINAN = "makineden_alinan"
    LABORATUVAR_TESTI = "laboratuvar_testi"
    KULLANICI_GIRISI = "kullanici_girisi"
    # Gerçek makine/PLC entegrasyonu bu fazda yok; simüle üretim verisi bu
    # etiketle işaretlenir ki 'Makineden Alınan' ile karıştırılmasın —
    # gerçek entegrasyon bağlandığında satır kaynağı MAKINEDEN_ALINAN'a döner.
    SIMULASYON_VERISI = "simulasyon_verisi"


class RecipeSource(StrEnum):
    REFERANS = "referans_receteden"
    URETILDI = "sistem_uretti"


class MetricType(StrEnum):
    CARBON = "karbon"
    WASTE = "fire"
    COST = "maliyet"
    ENERGY = "enerji"
    VIRGIN_USAGE = "virgin_kullanimi"
    PCR_USAGE = "pcr_kullanimi"
    REGRANULE_USAGE = "regranul_kullanimi"


class ProductionOrderStatus(StrEnum):
    BEKLIYOR = "bekliyor"
    DEVAM_EDIYOR = "devam_ediyor"
    TAMAMLANDI = "tamamlandi"


class PhysicalTestResult(StrEnum):
    PASSED = "basarili"
    FAILED = "basarisiz"
    PENDING = "beklemede"


class WasteType(StrEnum):
    """Faz B.6 — tipli fire kırılımı. `recoverable` varsayılanları
    `production_flow_service.WASTE_TYPE_RECOVERABLE_DEFAULT`'ta tutulur; bu
    enum sadece kabul edilen fire kategorilerini tanımlar (demo hatlarımız
    baskı/laminasyon yapmadığından o türler simülasyonda üretilmez, ama
    ileride gerçek entegrasyonla üretilebilecek kayıtlar için tanımlıdır)."""
    START_UP = "start_up"
    EDGE_TRIM = "kenar_firesi"
    ROLL_CHANGE = "bobin_degisimi"
    QUALITY_REJECT = "kalite_reddi"
    PRINTING = "baski_firesi"
    LAMINATION = "laminasyon_firesi"
    CUTTING = "kesim_firesi"
    PROCESS_ADJUSTMENT = "proses_ayari"
    CONTAMINATED = "kontamine"
