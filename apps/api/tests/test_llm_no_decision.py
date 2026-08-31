"""LLM'in yalnızca gerekçelendirme yaptığını, karar vermediğini doğrulayan
testler. Test ortamında ANTHROPIC_API_KEY tanımlı olmadığından
`llm_available()` False döner ve deterministik fallback'e düşülür — bu da
platformun LLM'e bağımlı çalışmadığının kanıtıdır."""
from app.llm.client import llm_available
from app.llm.justification import build_elimination_summary, build_finalist_justification


def test_llm_unavailable_in_test_environment():
    # Bu testin anlamlı olması için ortamda API anahtarı olmamalı (CI/test varsayımı).
    assert llm_available() is False


def test_finalist_justification_is_deterministic_and_grounded():
    data = {
        "composition_pct": {"virgin": 62.0, "pcr": 38.0, "regranul": 0.0},
        "score": 0.836,
        "score_breakdown": {"teknik_performans": 0.97},
        "data_confidence": "dusuk",
        "decision_basis": {
            "mevzuat_maddeleri": ["PPWR-ART-7"],
            "hat_parametreleri": {"hat": "Hat-1", "katman_yapisi": "A/B/A"},
        },
    }
    text1 = build_finalist_justification(data)
    text2 = build_finalist_justification(data)
    assert text1 == text2  # yeni bir "karar" üretmiyor, aynı veriden aynı metni çıkarıyor
    assert "38" in text1  # verilen PCR yüzdesi kullanılıyor
    assert "97" in text1  # verilen teknik performans skoru (0.97 -> 97/100) kullanılıyor
    assert "PPWR-ART-7" in text1
    assert "Hat-1" in text1 and "A/B/A" in text1
    # Önceki hata: decision_basis['hat_parametreleri'] (bir dict) ham haliyle
    # metne gömülüyordu -> "{'hat': 'Hat-1', ..." gibi Python söz dizimi görünüyordu.
    assert "{" not in text1 and "'hat':" not in text1


def test_finalist_justification_never_invents_numbers_not_in_input():
    data = {
        "composition_pct": {"virgin": 100.0, "pcr": 0.0, "regranul": 0.0},
        "score": 0.5,
        "score_breakdown": {},
        "data_confidence": "yuksek",
        "decision_basis": {},
    }
    text = build_finalist_justification(data)
    # Girişte olmayan, mevzuat/hat verisi olmadığından bu bölümler metne eklenmemeli.
    assert "PPWR" not in text
    assert "Hat" not in text


def test_elimination_summary_only_reflects_given_reasons():
    reasons = ["Gıda temaslı ambalajda iç katman gıda sınıfı sertifikasyonuna sahip değil."]
    summary = build_elimination_summary(reasons)
    assert summary == reasons[0]


def test_elimination_summary_with_no_reasons_indicates_pass():
    summary = build_elimination_summary([])
    assert "geçti" in summary.lower() or "kısıt" in summary.lower()
