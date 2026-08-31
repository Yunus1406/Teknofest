"""Dashboard 2: kullanıcı teknik şartname (PDF/metin) yüklediğinde, ambalaj
alanlarını (tür, kullanım alanı, boyut, gıda teması vb.) metinden çıkarır.
Kullanıcıya yalnızca eksik/şüpheli alanlar kontrol ettirilir — bu yüzden
model her alan için bir `confidence` (yuksek/orta/dusuk) döndürür."""
import json

from app.llm.client import complete_json_grounded, llm_available

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


def extract_fields_from_spec_text(spec_text: str) -> dict:
    if not llm_available():
        return dict(_EMPTY_RESULT)
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
        return dict(_EMPTY_RESULT)
