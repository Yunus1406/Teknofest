"""Faz S.1 (Madde 29) — QR Kodla Geri Dönüşüm Yönlendirmesi. Faz C.3'ün
DPP/QR altyapısı DEĞİŞTİRİLMEDEN GENİŞLETİLİR: QR kodun kendisi hâlâ sadece
pasaportun public URL'ini taşır (bkz. passport_service.py::_qr_data_uri),
bu modül o sayfanın tüketici (public) görünümüne eklenen SADE bir ek
bölümü hesaplar.

DÜRÜSTLÜK NOTU: `Polymer` modelinde bir "hangi kutuya atılır" alanı YOK,
`Company`de bölge bazlı bir yerel geri dönüşüm merkezi/link alanı YOK.
Aşağıdaki `_POLYMER_RECYCLING_INFO` sabit, kod-içi ve BÖLGEYE ÖZEL
DEĞİLDİR — genel, yaygın kabul görmüş polimer-aile bilgisidir; hiçbir
gerçek/uydurma URL veya yerel kurum adı üretilmez. Reçete birden fazla
farklı polimer ailesi içeriyorsa (çok katmanlı/bariyer yapı), tek bir
kutuya kesin bir yönlendirme YAPILMAZ -- bu durum dürüstçe belirtilir."""
from app.models.recipe import Recipe

_RECYCLING_DISCLAIMER = (
    "Bu bilgi tüketiciye yönelik genel bir yönlendirmedir; PPWR zorunlu "
    "Dijital Ürün Pasaportu ya da resmi bir geri dönüşüm sertifikasyonu "
    "DEĞİLDİR."
)

_GENEL_YEREL_YONLENDIRME = (
    "Sistemde bölgenize özel bir geri dönüşüm merkezi/toplama noktası kaydı "
    "bulunmuyor -- ambalajı yerel belediyenizin atık ayrıştırma/geri "
    "dönüşüm rehberine göre ayırmanız önerilir."
)

# Yaygın, genel kabul görmüş polimer-aile bilgisi -- bölgeye özel DEĞİL.
_POLYMER_RECYCLING_INFO: dict[str, dict[str, str]] = {
    "PE": {"malzeme_aciklamasi": "PE film, geri dönüşüme uygun.", "kutu_talimati": "Plastik geri dönüşüm kutusu."},
    "LDPE": {"malzeme_aciklamasi": "LDPE (yumuşak polietilen) film, geri dönüşüme uygun.", "kutu_talimati": "Plastik geri dönüşüm kutusu."},
    "LLDPE": {"malzeme_aciklamasi": "LLDPE (doğrusal düşük yoğunluklu polietilen) film, geri dönüşüme uygun.", "kutu_talimati": "Plastik geri dönüşüm kutusu."},
    "mLLDPE": {"malzeme_aciklamasi": "mLLDPE film, geri dönüşüme uygun.", "kutu_talimati": "Plastik geri dönüşüm kutusu."},
    "HDPE": {"malzeme_aciklamasi": "HDPE (yüksek yoğunluklu polietilen), geri dönüşüme uygun.", "kutu_talimati": "Plastik geri dönüşüm kutusu."},
    "MDPE": {"malzeme_aciklamasi": "MDPE (orta yoğunluklu polietilen), geri dönüşüme uygun.", "kutu_talimati": "Plastik geri dönüşüm kutusu."},
    "PP": {"malzeme_aciklamasi": "PP (polipropilen), geri dönüşüme uygun.", "kutu_talimati": "Plastik geri dönüşüm kutusu."},
    "CPP": {"malzeme_aciklamasi": "CPP (kalender polipropilen) film, geri dönüşüme uygun.", "kutu_talimati": "Plastik geri dönüşüm kutusu."},
    "BOPP": {"malzeme_aciklamasi": "BOPP (biyoeksenli polipropilen) film, geri dönüşüme uygun.", "kutu_talimati": "Plastik geri dönüşüm kutusu."},
    "PET": {"malzeme_aciklamasi": "PET, geri dönüşüme uygun.", "kutu_talimati": "Plastik geri dönüşüm kutusu."},
    "PLA": {"malzeme_aciklamasi": "PLA, bitki bazlı kompostlanabilir bir malzemedir.", "kutu_talimati": "Standart plastik kutusuna DEĞİL — kompost/organik atık akışına uygunsa oraya (yerel imkana bağlı)."},
}

_BILINMEYEN_POLIMER_NOT = "Bu malzeme için genel bir ayrıştırma bilgisi sistemde tanımlı değil."
_KARMA_YAPI_NOT = (
    "Bu ambalaj birden fazla farklı malzeme türü içerir (çok katmanlı yapı); "
    "tek bir geri dönüşüm kutusuna kesin bir yönlendirme yapılamıyor — yerel "
    "geri dönüşüm rehberinize danışın."
)


def build_recycling_guidance(recipe: Recipe) -> dict:
    polymer_codes = sorted({layer.material.polymer.code for layer in recipe.layers if layer.material is not None})

    if not polymer_codes:
        malzeme_aciklamasi = "Bu reçete için hammadde bilgisi bulunamadı."
        kutu_talimati = _BILINMEYEN_POLIMER_NOT
    elif len(polymer_codes) == 1:
        info = _POLYMER_RECYCLING_INFO.get(polymer_codes[0])
        if info is not None:
            malzeme_aciklamasi = info["malzeme_aciklamasi"]
            kutu_talimati = info["kutu_talimati"]
        else:
            malzeme_aciklamasi = f"{polymer_codes[0]} bazlı ambalaj."
            kutu_talimati = _BILINMEYEN_POLIMER_NOT
    else:
        malzeme_aciklamasi = f"Çok katmanlı yapı: {', '.join(polymer_codes)}."
        kutu_talimati = _KARMA_YAPI_NOT

    return {
        "malzeme_aciklamasi": malzeme_aciklamasi,
        "kutu_talimati": kutu_talimati,
        "yerel_yonlendirme": _GENEL_YEREL_YONLENDIRME,
        "aciklama": _RECYCLING_DISCLAIMER,
    }
