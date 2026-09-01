"""Dashboard 2: kullanıcı teknik şartname (PDF/metin) yüklediğinde, ambalaj
alanlarını (tür, kullanım alanı, boyut, gıda teması vb.) metinden çıkarır.
Kullanıcıya yalnızca eksik/şüpheli alanlar kontrol ettirilir — bu yüzden
model her alan için bir `confidence` (yuksek/orta/dusuk) döndürür."""
import json
import re

from app.llm.client import complete_json_grounded, llm_available
from app.services.common import _PACKAGING_KEYWORD_RULES

_EXTRACTION_SYSTEM_PROMPT = """Sen bir ambalaj mühendisliği teknik şartname
okuyucususun. Sana serbest metin halinde bir teknik şartname veriliyor.
Aşağıdaki alanları JSON olarak çıkar:

{
  "packaging_type": string | null,
  "usage_area": string | null,
  "product": string | null,
  "target_market": string | null,
  "food_contact": boolean | null,
  "target_volume_units": number | null,
  "dimensions": {"length_mm": number|null, "width_mm": number|null, "height_mm": number|null},
  "target_thickness_micron": number | null,
  "target_gsm": number | null,
  "physical_performance_notes": string | null,
  "field_confidence": {"<alan_adi>": "yuksek"|"orta"|"dusuk"}
}

KURALLAR:
- Metinde açıkça yazmayan bir alan için değer UYDURMA, null bırak ve confidence "dusuk" yap.
- Sadece geçerli JSON döndür, başka metin ekleme.
- field_confidence her dolu alan için modelin bu çıkarıma ne kadar güvendiğini belirtir."""

_EMPTY_RESULT = {
    "packaging_type": None,
    "usage_area": None,
    "product": None,
    "target_market": None,
    "food_contact": None,
    "target_volume_units": None,
    "dimensions": {"length_mm": None, "width_mm": None, "height_mm": None},
    "target_thickness_micron": None,
    "target_gsm": None,
    "physical_performance_notes": None,
    "field_confidence": {},
}


def _regex_fallback_extract(spec_text: str) -> dict:
    """LLM kullanılamadığında (ör. ANTHROPIC_API_KEY tanımlı değil — bu dev
    ortamında hep böyle) devreye giren basit regex/anahtar-kelime tabanlı bir
    çıkarım. Hiçbir alan UYDURULMAZ: bulunamayan alan None kalır. Bulunan her
    alan "dusuk" güvenle işaretlenir -- kullanıcı Aşama 2'nin inceleme
    ekranında bunu görüp doğrulamalı, hiçbir alan otomatik kabul edilmez."""
    result = dict(_EMPTY_RESULT)
    result["dimensions"] = dict(_EMPTY_RESULT["dimensions"])
    confidence: dict[str, str] = {}
    lowered = spec_text.lower()

    for keyword, _category, _prefs in _PACKAGING_KEYWORD_RULES:
        if keyword in lowered:
            result["packaging_type"] = keyword
            confidence["packaging_type"] = "dusuk"
            break

    if re.search(r"avrupa\s*birli[gğ]i|\bab\b", lowered):
        result["target_market"] = "AB"
        confidence["target_market"] = "dusuk"
    elif re.search(r"t[üu]rkiye", lowered):
        result["target_market"] = "Türkiye"
        confidence["target_market"] = "dusuk"
    elif re.search(r"\babd\b|amerika", lowered):
        result["target_market"] = "ABD"
        confidence["target_market"] = "dusuk"

    if "gıda" in lowered or "gida" in lowered:
        result["food_contact"] = True
        confidence["food_contact"] = "dusuk"

    thickness_match = re.search(r"(\d+[.,]?\d*)\s*(µm|um|mikron|micron)", lowered)
    if thickness_match:
        result["target_thickness_micron"] = float(thickness_match.group(1).replace(",", "."))
        confidence["target_thickness_micron"] = "dusuk"

    gsm_match = re.search(r"(\d+[.,]?\d*)\s*(g\s*/\s*m2|g\s*/\s*m²|gsm|gr\s*/\s*m2)", lowered)
    if gsm_match:
        result["target_gsm"] = float(gsm_match.group(1).replace(",", "."))
        confidence["target_gsm"] = "dusuk"

    volume_match = re.search(r"(\d[\d.,]*)\s*(adet|birim)", lowered)
    if volume_match:
        try:
            volume = int(float(volume_match.group(1).replace(".", "").replace(",", ".")))
        except ValueError:
            pass
        else:
            result["target_volume_units"] = volume
            confidence["target_volume_units"] = "dusuk"

    result["field_confidence"] = confidence
    return result


def extract_fields_from_spec_text(spec_text: str) -> dict:
    if not llm_available():
        return _regex_fallback_extract(spec_text)
    try:
        raw = complete_json_grounded(
            _EXTRACTION_SYSTEM_PROMPT, {"sartname_metni": spec_text[:8000]}, max_tokens=600
        )
        # Model bazen kod bloğu içine sarabilir; temizle.
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        merged = dict(_EMPTY_RESULT)
        merged.update(parsed)
        return merged
    except Exception:
        return _regex_fallback_extract(spec_text)
