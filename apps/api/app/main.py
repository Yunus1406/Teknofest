from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.db import engine
from app.models import Base

settings = get_settings()

# Faz 1: Alembic migration akışı kurulu (bkz. alembic/), ama yerel/demo
# geliştirmede tabloların var olduğundan emin olmak için create_all de
# çağrılır (idempotent — var olan tabloyu bozmaz).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Reçete OS API",
    description="Ambalaj Sürdürülebilirlik Optimizasyon Platformu — Bilgi Tabanı, "
    "Kısıt Motoru ve Optimizasyon servisleri.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
