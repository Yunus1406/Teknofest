from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Uygulama ayarları. .env dosyasından okunur; okunamayan alanlar için
    üretime hazır (Postgres/Anthropic) varsayılanlar yerine güvenli yerel
    varsayılanlar kullanılır ki proje docker olmadan da ayağa kalkabilsin."""

    model_config = SettingsConfigDict(
        env_file=str(API_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # Varsayılan: yerel dosya tabanlı SQLite. Docker Compose ortamında
    # infra/docker-compose.yml, DATABASE_URL'i Postgres'e çevirir.
    database_url: str = f"sqlite:///{(API_DIR / 'recete_os.db').as_posix()}"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    llm_disabled: bool = False

    cors_origins: list[str] = ["http://localhost:3000"]

    # Faz C.1 — Dijital Ürün Pasaportu. QR kodun hedeflediği genel web
    # sayfasının kök adresi (frontend'in `/dpp/{passport_no}` rotası).
    public_web_base_url: str = "http://localhost:3000"
    # Yetkili Alan (ticari hammadde grade/lot/tedarikçi detayları) erişim
    # anahtarı. Gerçek bir kullanıcı/oturum sistemi DEĞİLDİR — MVP kapsamı:
    # tek bir paylaşılan sabit anahtar. None ise (varsayılan) authorized
    # alan HİÇBİR istekte açılmaz — bu güvenli varsayılandır, prod'da
    # `.env`'de mutlaka set edilmelidir.
    dpp_authorized_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
