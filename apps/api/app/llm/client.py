"""Anthropic API istemcisi. LLM burada YALNIZCA hesaplanmış/kural motorundan
gelen verileri insan diline çevirmek için kullanılır — karar vermez.
ANTHROPIC_API_KEY tanımlı değilse veya LLM_DISABLED=true ise, sistem
çökmesin diye deterministik bir fallback metne düşer (demo/CI ortamı)."""
import json

from app.core.config import get_settings

_settings = get_settings()

_client = None
if _settings.anthropic_api_key and not _settings.llm_disabled:
    from anthropic import Anthropic

    _client = Anthropic(api_key=_settings.anthropic_api_key)


def llm_available() -> bool:
    return _client is not None


def complete_json_grounded(system_prompt: str, data: dict, max_tokens: int = 400) -> str:
    """Verilen `data` sözlüğünü kullanıcı mesajı olarak JSON halinde yollar;
    modelden yalnızca bu veriye dayanan, yeni sayı/iddia içermeyen kısa bir
    Türkçe metin ister. LLM kullanılamıyorsa fallback metin döner (çağıran
    fonksiyonlar fallback'i data'dan kendileri üretir, bkz. justification.py)."""
    if _client is None:
        raise RuntimeError("LLM_UNAVAILABLE")

    message = _client.messages.create(
        model=_settings.anthropic_model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": (
                    "Aşağıdaki hesaplanmış/kural motoru verisine dayanarak yanıt ver:\n\n"
                    + json.dumps(data, ensure_ascii=False, indent=2)
                ),
            }
        ],
    )
    parts = [block.text for block in message.content if getattr(block, "type", None) == "text"]
    return "".join(parts).strip()
