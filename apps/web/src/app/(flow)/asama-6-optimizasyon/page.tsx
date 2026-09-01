"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { OptimizationRunOut } from "@/lib/types";
import { ActiveCaseSummary } from "@/components/layout/ActiveCaseSummary";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { StatTile } from "@/components/ui/StatTile";
import { Badge } from "@/components/ui/Badge";
import { FunnelChart } from "@/components/visualizations/FunnelChart";
import {
  dataConfidenceFromSourceKind,
  dataConfidenceLabel,
  dataConfidenceTone,
  eliminationCategoryLabel,
  eliminationCategoryTone,
  tierLabel,
} from "@/lib/labels";
import { useCaseStore } from "@/stores/case-store";

export default function Stage6Page() {
  const packagingRequestId = useCaseStore((s) => s.packagingRequestId);
  const lineId = useCaseStore((s) => s.lineId);
  const lineEligible = useCaseStore((s) => s.lineEligible);
  const setOptimizationRunId = useCaseStore((s) => s.setOptimizationRunId);
  const setRecipeId = useCaseStore((s) => s.setRecipeId);

  const [run, setRun] = useState<OptimizationRunOut | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Faz K.8 (Madde 10) — uyumlu üretim hattı yoksa optimizasyon HİÇ
    // başlatılmaz (aşağıdaki gate mesajı gösterilir).
    if (!packagingRequestId || !lineId || !lineEligible || run) return;
    setRunning(true);
    api
      .runOptimization(packagingRequestId, lineId, 10)
      .then((r) => {
        setRun(r);
        setOptimizationRunId(r.id);
        if (r.finalists[0]) setRecipeId(r.finalists[0].recipe.id);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setRunning(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [packagingRequestId, lineId, lineEligible]);

  const eliminatedCount = run ? run.generated_candidate_count - run.survived_constraint_engine_count : 0;

  return (
    <div>
      <StageHeader
        no={6}
        title="Optimizasyon (Ana Motor)"
        description="Virgin/PCR/regranül oranları, katman dağılımları ve mikron/gramaj kombinasyonları üretilir; her aday teknik performans, üretilebilirlik, mevzuat, kaynak kullanımı, karbon, fire ve maliyet açısından değerlendirilir."
      />
      <ActiveCaseSummary />

      {(!packagingRequestId || !lineId) && (
        <Card className="border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">Önce Aşama 2-5&apos;i tamamlamalısınız.</p>
        </Card>
      )}
      {packagingRequestId && lineId && !lineEligible && (
        <Card className="border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">
            ⛔ Optimizasyon başlatılamıyor. Uyumlu üretim hattı bulunamadı — Aşama 4&apos;e dönüp uyumlu bir hat
            seçin.
          </p>
        </Card>
      )}
      {running && (
        <Card className="mb-6">
          <p className="text-sm text-ink/60">
            Kısıt motoru + çok amaçlı optimizasyon çalışıyor — aday reçeteler üretiliyor, kesin teknik ve
            malzeme-proses kısıtlarına göre eleniyor, kalanlar puanlanıyor…
          </p>
        </Card>
      )}
      {error && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      {run && (
        <>
          {/* Faz M.1 (Madde 11) — "343 aday üretildi" tek başına yanıltıcı bir
              büyük sayı izlenimi veriyordu. Ön Filtreleme (uyumluluk zincirinden
              geçen "teknik olarak mümkün" adaylar) ile Optimizasyon (bunlar
              arasından çok kriterli skorlamayla seçilen finalistler) artık iki
              ayrı, adı açıkça etiketlenmiş blok olarak gösteriliyor. */}
          <div className="mb-4">
            <p className="mb-2 font-mono text-xs font-semibold uppercase tracking-wide text-petrol/70">
              1. Ön Filtreleme — Uyumluluk Zinciri
            </p>
            <div className="grid grid-cols-3 gap-4">
              <StatTile label="Üretilen Aday (Teorik Kombinasyon)" value={run.generated_candidate_count} />
              <StatTile label="Elenen" value={eliminatedCount} tone={eliminatedCount > 0 ? "warn" : "default"} />
              <StatTile label="Teknik Olarak Mümkün" value={run.survived_constraint_engine_count} />
            </div>
          </div>
          <div className="mb-4">
            <p className="mb-2 font-mono text-xs font-semibold uppercase tracking-wide text-petrol/70">
              2. Optimizasyon — Çok Kriterli Skorlama
            </p>
            <div className="grid grid-cols-3 gap-4">
              <StatTile label="Değerlendirilen Aday" value={run.survived_constraint_engine_count} />
              <StatTile
                label="Seçilen Finalist"
                value={run.finalists.length}
                tone={run.finalists.length === 0 ? "warn" : "default"}
              />
              <div />
            </div>
          </div>
          <Card className="mb-6 border-petrol/15 bg-petrol/5">
            <p className="text-sm text-ink">
              <strong>Ön Filtreleme:</strong> {run.generated_candidate_count} teorik kombinasyondan{" "}
              {run.survived_constraint_engine_count}&apos;i teknik olarak mümkün → <strong>Optimizasyon:</strong>{" "}
              {run.survived_constraint_engine_count} adaydan {run.finalists.length} finalist seçildi.
            </p>
          </Card>
          <div className="mb-6">
            <Badge tone={dataConfidenceTone(dataConfidenceFromSourceKind("hesaplanan"))}>
              {dataConfidenceLabel(dataConfidenceFromSourceKind("hesaplanan"))}
            </Badge>
          </div>

          {/* Faz M.2 (Madde 12) — sayısal metnin YANINDA (yerine değil) görsel
              bir daralma gösterimi + TÜM elenenlerin kategorik dağılımı. */}
          <Card className="mb-6">
            <CardTitle subtitle="Adayların üç aşamadaki daralması ve elenen adayların hangi kısıt kategorisine düştüğü.">
              Huni Görünümü
            </CardTitle>
            <FunnelChart
              stages={[
                { label: "Üretilen Aday", value: run.generated_candidate_count, tone: "petrol" },
                { label: "Teknik Olarak Mümkün", value: run.survived_constraint_engine_count, tone: "virgin" },
                { label: "Seçilen Finalist", value: run.finalists.length, tone: "pcr" },
              ]}
            />
            {eliminatedCount > 0 && (
              <div className="mt-4 border-t border-ink/10 pt-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">
                  {eliminatedCount} Eleme — Kategorik Dağılım
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(run.elimination_category_counts)
                    .filter(([, count]) => count > 0)
                    .sort(([, a], [, b]) => b - a)
                    .map(([category, count]) => (
                      <Badge key={category} tone={eliminationCategoryTone(category)}>
                        {count} {eliminationCategoryLabel(category)}
                      </Badge>
                    ))}
                </div>
              </div>
            )}
          </Card>

          {run.generation_breakdown && (
            <Card className="mb-6">
              <CardTitle subtitle="Her katman pozisyonu için uygun hammadde + oran alternatiflerinin kartezyen çarpımı — bu sayı ürünün gerçek hammadde/hat verisi değiştikçe değişir.">
                Adaylar Nasıl Oluşturuldu?
              </CardTitle>
              <p className="text-tabular text-sm font-medium text-ink">{run.generation_breakdown.formula_text}</p>
              <ul className="mt-3 space-y-1">
                {run.generation_breakdown.layers.map((l, i) => (
                  <li key={i} className="text-xs text-ink/60">
                    Katman {l.layer_label}: {l.virgin_material_name}
                    {l.recycled_material_names.length > 0 && ` + ${l.recycled_material_names.join(", ")}`} →{" "}
                    <span className="text-tabular font-medium text-ink">{l.variant_count} seçenek</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card className="mb-6">
            <CardTitle subtitle="Kesin Teknik Kısıt ve Malzeme-Proses Kısıtı nedeniyle elenen, öne çıkan örnekler.">
              Neden Elendi? (örnekler)
            </CardTitle>
            {run.notable_eliminated.length === 0 ? (
              <p className="text-sm text-ink/50">Bu koşuda eleme örneği yok.</p>
            ) : (
              <ul className="space-y-3">
                {run.notable_eliminated.map((e, i) => (
                  <li key={i} className="rounded-lg bg-warn/5 p-3">
                    <p className="font-mono text-xs text-ink/50">{e.composition_summary}</p>
                    {/* Faz J.0 — her gerekçenin GERÇEK EvaluationTier'ı (Kesin
                        Teknik Kısıt / Malzeme-Proses Kısıtı) ayrı ayrı gösterilir. */}
                    {e.reasons.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {Array.from(new Set(e.reasons.map((r) => r.tier))).map((tier) => (
                          <Badge key={tier} tone={tier === "kesin_teknik_kisit" ? "warn" : "virgin"}>
                            {tierLabel(tier)}
                          </Badge>
                        ))}
                      </div>
                    )}
                    <p className="mt-1 text-sm text-ink/70">{e.summary_text}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* Faz M.3 (Madde 13) — 0 finalist durumunda boş/anlamsız bir "Sonuç"
              kartı yerine somut, aksiyon alınabilir bir Teşhis Ekranı. */}
          {run.diagnosis ? (
            <Card className="border-warn/40 bg-warn/5">
              <div className="flex items-center justify-between">
                <CardTitle subtitle="Optimizasyon 0 uygun aday üretti — aşağıda hangi kısıtın adayları elediği ve somut bir öneri var.">
                  ⚠ Teşhis Ekranı
                </CardTitle>
                <Badge tone="warn">0 finalist</Badge>
              </div>
              {run.diagnosis.dominant_reason_text && (
                <p className="mt-2 text-sm text-ink/80">
                  <strong>En sık neden{run.diagnosis.affected_pct != null ? ` (%${run.diagnosis.affected_pct})` : ""}:</strong>{" "}
                  {run.diagnosis.dominant_reason_text}
                </p>
              )}
              {run.diagnosis.alternative_line_name && (
                <p className="mt-2 text-sm text-pcr">
                  ✓ Alternatif: <strong>{run.diagnosis.alternative_line_name}</strong>
                  {run.diagnosis.alternative_line_score_pct != null && ` (%${run.diagnosis.alternative_line_score_pct} uyumlu)`} —
                  Aşama 4&apos;e dönüp bu hattı seçebilirsiniz.
                </p>
              )}
              <p className="mt-3 rounded-lg bg-white/60 p-3 text-sm text-ink/70">{run.diagnosis.suggestion_text}</p>
            </Card>
          ) : (
            <Card>
              <div className="flex items-center justify-between">
                <CardTitle subtitle="Kısıt motorundan geçen adaylar arasından en yüksek skorlu 3-4 alternatif seçildi.">
                  Sonuç
                </CardTitle>
                <Badge tone="pcr">{run.finalists.length} finalist</Badge>
              </div>
              <p className="text-sm text-ink/60">
                Detaylı reçete önerileri, gerekçeleri ve karar dayanağı için sonraki aşamaya geçin.
              </p>
            </Card>
          )}
        </>
      )}

      <StageNav currentNo={6} nextEnabled={!!run && run.finalists.length > 0} />
    </div>
  );
}
