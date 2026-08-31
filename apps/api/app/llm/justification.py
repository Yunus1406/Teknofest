"""'Neden Bu Reçete?' / 'Neden Elendi?' gerekçelendirme metinleri.

Kritik ilke: LLM karar vermez, sadece optimizasyon motorunun ürettiği
sayısal/kuralsal sonucu insan diline çevirir. Sistem promptu modele YENİ bir
sayı, eşik veya iddia üretmemesini açıkça söyler; LLM kullanılamıyorsa
(API anahtarı yok / LLM_DISABLED) deterministik bir şablon fallback'e düşülür
— platform hiçbir zaman LLM'e bağımlı çalışmaz durumuna gelmez."""
from app.llm.client import complete_json_grounded, llm_available

_JUSTIFICATION_SYSTEM_PROMPT = """Sen bir ambalaj mühendisliği asistanısın. Görevin,
sana verilen JSON içindeki HESAPLANMIŞ sonuçları (kısıt motoru + optimizasyon skoru)
2-3 cümlelik akıcı Türkçe metne çevirmektir.

KURALLAR:
- Sadece verilen JSON'daki sayı, oran, kural adı ve mevzuat kodlarını kullan.
- Yeni bir sayı, yüzde, eşik değer ya da iddia UYDURMA.
- Bir karar VERME; sadece verilen kararı (neden seçildiğini/elendiğini) gerekçelendir.
- Teknik ama anlaşılır bir üslup kullan, pazarlama dili kullanma.
- Yanıtın sadece istenen metin olsun, başlık/madde işareti ekleme."""

_ELIMINATION_SYSTEM_PROMPT = """Sen bir ambalaj mühendisliği asistanısın. Sana bir
aday reçetenin kısıt motoru tarafından elenme gerekçeleri (JSON liste) veriliyor.
Bunları 1-2 cümlelik, sade Türkçe bir özete çevir.

KURALLAR:
- Sadece verilen gerekçe metinlerini özetle/birleştir, yeni sayı veya iddia ekleme.
- Elenme kararını sen vermiyorsun, zaten verilmiş kararı özetliyorsun.
- Yanıtın sadece istenen metin olsun."""


_CONFIDENCE_LABELS = {"yuksek": "Yüksek", "orta": "Orta", "dusuk": "Düşük"}


def _fallback_justification(data: dict) -> str:
    """LLM kullanılamadığında (API anahtarı yok / hata) düşülen deterministik
    şablon. Önceki hata: `decision_basis['hat_parametreleri']` (bir Python
    dict) doğrudan f-string içine gömülüyordu — ekranda
    "{'hat': 'Hat-2...', 'katman_yapisi': 'A/B/A'}" gibi ham veri görünüyordu.
    Artık her alan tek tek, doğal Türkçe cümlelere çevrilir."""
    comp = data.get("composition_pct", {})
    basis = data.get("decision_basis", {})
    breakdown = data.get("score_breakdown", {})
    confidence = data.get("data_confidence")

    sentences: list[str] = []

    tech_score = breakdown.get("teknik_performans")
    if tech_score is not None:
        sentences.append(f"Tahmini teknik performans {tech_score * 100:.0f}/100 ile kabul edilebilir düzeydedir.")

    pcr_pct = comp.get("pcr", 0.0)
    pir_pct = comp.get("regranul", 0.0)
    recycled_parts = []
    if pcr_pct > 0.01:
        recycled_parts.append(f"%{pcr_pct:.0f} PCR")
    if pir_pct > 0.01:
        recycled_parts.append(f"%{pir_pct:.0f} PIR-regranül")
    if recycled_parts:
        sentences.append(" ve ".join(recycled_parts) + " ile virgin hammadde kullanımını azaltmaktadır.")
    else:
        sentences.append("Tamamen virgin hammaddeden oluşmaktadır.")

    hat_params = basis.get("hat_parametreleri") or {}
    hat_name = hat_params.get("hat")
    layer_structure = hat_params.get("katman_yapisi")
    if hat_name and layer_structure:
        sentences.append(f"{hat_name} hattında, {layer_structure} katman yapısında üretilebilir durumdadır.")
    elif hat_name:
        sentences.append(f"{hat_name} hattında üretilebilir durumdadır.")

    if basis.get("mevzuat_maddeleri"):
        sentences.append(
            "İlgili mevzuat maddelerinden (" + ", ".join(basis["mevzuat_maddeleri"]) + ") ön kontrolden geçmiştir."
        )

    if confidence in _CONFIDENCE_LABELS:
        sentences.append(f"Veri güveni: {_CONFIDENCE_LABELS[confidence]}.")

    return " ".join(sentences)


def build_finalist_justification(data: dict) -> str:
    """`data` örneği:
    {
      "composition_pct": {"virgin": 70, "pcr": 20, "regranul": 10},
      "score": 0.78,
      "score_breakdown": {...},
      "data_confidence": "orta",
      "decision_basis": {
         "mevzuat_maddeleri": ["PPWR-ART-7"],
         "hat_parametreleri": {"hat": "Hat-1", "katman_yapisi": "A/B/A"},
         "gecmis_receteler": []
      }
    }
    """
    if not llm_available():
        return _fallback_justification(data)
    try:
        return complete_json_grounded(_JUSTIFICATION_SYSTEM_PROMPT, data)
    except Exception:
        return _fallback_justification(data)


def _fallback_elimination_summary(reasons: list[str]) -> str:
    if not reasons:
        return "Bu aday, kısıt motoru kontrollerinin tamamından geçti."
    if len(reasons) == 1:
        return reasons[0]
    return reasons[0] + f" (+{len(reasons) - 1} ek gerekçe)"


def build_elimination_summary(reasons: list[str]) -> str:
    if not llm_available():
        return _fallback_elimination_summary(reasons)
    try:
        return complete_json_grounded(_ELIMINATION_SYSTEM_PROMPT, {"gerekceler": reasons})
    except Exception:
        return _fallback_elimination_summary(reasons)
