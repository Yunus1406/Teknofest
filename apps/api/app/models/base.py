import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Tüm ORM modellerinin ortak atası.

    PK stratejisi: taşınabilir String(36) UUID (SQLite yerel geliştirmede,
    Postgres üretimde aynı şekilde çalışır).
    JSON alanları: sqlalchemy.JSON kullanılır (SQLite'ta TEXT, Postgres'te
    JSONB'ye map edilebilir) — şartname/özellik gibi esnek alanlar için.
    """

    type_annotation_map = {
        dict: JSON,
        list: JSON,
    }


class IdMixin:
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
