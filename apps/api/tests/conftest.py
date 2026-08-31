"""DB'ye ihtiyaç duyan servis testleri için ortak fixture'lar. Her test
kendi izole edilmiş, dosya tabanlı olmayan SQLite belleği üzerinde çalışır."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base


@pytest.fixture()
def db_session():
    # StaticPool ŞART: aksi halde her yeni connection checkout'u (ör. bir
    # commit'ten sonra, ya da FastAPI TestClient bir istek işlerken) SQLite
    # ':memory:' için TAMAMEN AYRI/boş bir veritabanına bağlanır -- "no such
    # table" hatasının kökeni budur. StaticPool tüm engine ömrü boyunca TEK
    # bir fiziksel bağlantıyı paylaştırır.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
