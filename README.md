# Reçete OS — Ambalaj Sürdürülebilirlik Optimizasyon Platformu

Mimari detaylar için bkz. [`docs/architecture.md`](docs/architecture.md).

## Gereksinimler

- Python 3.12+ (proje 3.14 ile test edildi)
- Node.js 20+
- (Opsiyonel, üretim/Docker akışı için) Docker + Docker Compose

## Backend (apps/api)

```bash
cd apps/api
python -m venv .venv
./.venv/Scripts/activate          # Windows
pip install -r requirements.txt

# Bilgi tabanını + demo hat/malzeme/ambalaj talebini yükle (opsiyonel ama önerilir)
python scripts/seed_demo.py

# API'yi başlat
uvicorn app.main:app --reload --port 8000
```

`ANTHROPIC_API_KEY` tanımlanmazsa (bkz. `.env.example`), sistem şartname
çıkarımı ve reçete gerekçelendirmesi için deterministik fallback metne düşer —
kısıt motoru ve optimizasyon tam olarak çalışmaya devam eder.

Testleri çalıştırmak için: `pytest`

## Frontend (apps/web)

```bash
npm install                 # repo kökünden (npm workspaces)
npm run dev:web              # ya da: cd apps/web && npm run dev
```

`apps/web/.env.local` içine `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
eklemeniz gerekebilir (varsayılan zaten bu adres).

Uygulama http://localhost:3000 adresinde açılır ve otomatik olarak
Aşama 1 (Ana Ekran)'a yönlenir.

## Docker Compose (Postgres + API)

```bash
cd infra
docker compose up --build
```
