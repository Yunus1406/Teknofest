# Mimari Notları — Reçete OS

Bu doküman, onaylanan mimari planın (bkz. proje geçmişi) gerçek kod tabanına nasıl
yansıdığını özetler.

## Servisler

- `apps/web` — Next.js 14 (App Router) + TypeScript + Tailwind CSS + Zustand.
- `apps/api` — FastAPI + SQLAlchemy 2.0 + Pydantic v2 + Alembic.
- Veritabanı: yerel geliştirmede SQLite (varsayılan, `apps/api/recete_os.db`),
  Docker Compose ortamında Postgres 16 (`infra/docker-compose.yml`).
- LLM: Anthropic API (`claude-sonnet-5`), yalnızca `apps/api/app/llm/` içinde —
  şartname alan çıkarımı (Aşama 2) ve reçete gerekçelendirme (Aşama 7) için.
  API anahtarı tanımlı değilse sistem deterministik fallback metne düşer;
  hiçbir zaman LLM'e bağımlı çalışmaz.

## Çekirdek motor (Aşama 6-7'nin gerçek teslimatı)

1. **Bilgi Tabanı** (`app/knowledge_base/`) — YAML seed verisi (polimerler,
   virgin/PCR/regranül malzemeler, katkılar, PPWR'nin kritik maddeleri),
   `loader.py` ile DB'ye idempotent yüklenir.
2. **Kısıt Motoru** (`app/constraint_engine/`) — ORM'den tamamen bağımsız,
   saf/test edilebilir dataclass'lar (`types.py`) üzerinde çalışan kural
   fonksiyonları (`rules.py`). Üç kategori: Kesin Teknik Kısıt, Malzeme-Proses
   Kısıtı (mevzuat/gıda teması dahil), ve elemeyen Tahmini Fiziksel Performans
   (skorlama katmanına bırakılır).
3. **Optimizasyon** (`app/optimization/`) — `candidate_generator.py` katman
   yapısına göre virgin/geri dönüşüm oranı taraması yapıp aday üretir;
   `scorer.py` çok kriterli ağırlıklı skor + "Veri Güveni" etiketi hesaplar.
4. **Gerekçelendirme** (`app/llm/justification.py`) — hesaplanmış veriyi
   Türkçe'ye çevirir; karar vermez (bkz. `tests/test_llm_no_decision.py`).

Orkestrasyon `app/services/optimization_service.py`'de birleşir: aday üretimi →
kısıt filtresi → skorlama → en iyi 3-4 finalist + öne çıkan elenenler →
DB'ye kalıcı yazım (Recipe + RecipeLayer + RecipeEvaluation + RecipeMetric +
OptimizationRun/Candidate).

## Genişletilebilirlik (gelecekteki ML modeli için)

`recipe_evaluations`, `recipe_metrics`, `physical_tests`, `sustainability_results`
tabloları **append-only**'dir (hiç üzerine yazılmaz) ve `recipes` kendi
`version`/`parent_recipe_id` soyunu tutar. Gerçek üretim + doğrulama verisi
biriktikçe, bu tablolardan doğrudan "reçete özellikleri → gerçek sonuç" eğitim
seti çıkarılabilir; kural motorunun üzerine bir tahmin modeli (scikit-learn
regresyon) `app/optimization/scorer.py`'nin yanına yeni bir modül olarak
eklenebilir, mevcut şema değişmeden.

## Faz 1 kapsam durumu

| Aşama | Durum |
|---|---|
| 1 Ana Ekran | Gerçek (DB agregasyonu) |
| 2 Ambalaj Tanımlama | Gerçek (form + LLM destekli şartname çıkarımı) |
| 3 Mevzuat | Gerçek (kural tabanlı değerlendirme) |
| 4 Altyapı Eşleştirme | Gerçek |
| 5 Akıllı Başlangıç | Gerçek (referans reçete varsa kopyalar, yoksa güvenli virgin taban üretir) |
| 6-7 Optimizasyon & Öneriler | **Gerçek — ana teslimat** |
| 8 Karşılaştırma | Gerçek hesap, "Tahmini" etiketli |
| 9 Üretime Aktarım | Gerçek (mock hat/makine seçimi onayı) |
| 10 Canlı Takip | Simüle (şema gerçek entegrasyona hazır) |
| 11 Fiziksel Doğrulama | Gerçek versiyonlama mantığı, test verisi kullanıcı girişi/mock |
| 12 Nihai Sonuç | Gerçek agregasyon, girdiler mock/kullanıcı kaynaklı |

## Bilinen tasarım kısıtı (renk erişilebilirliği)

Zorunlu marka paleti içindeki regranül grisi (#8A8F82) ile PCR yeşili
(#3E8F63), renk körlüğü açısından ayırt edilmesi güç bir çift (bkz. dataviz
doğrulayıcı sonucu — ΔE eşiklerinin altında). Renkler kullanıcı talebiyle
sabit tutuldu; risk, `LayeredCompositionBar` bileşeninde her segmentin daima
metin etiketi/lejant taşıması ve regranül bandına 45° dokulu bir desen
eklenmesiyle azaltıldı (bkz. `apps/web/src/components/visualizations/LayeredCompositionBar.tsx`).
