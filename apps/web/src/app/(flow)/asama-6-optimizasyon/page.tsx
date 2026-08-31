"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { OptimizationRunOut } from "@/lib/types";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { StatTile } from "@/components/ui/StatTile";
import { Badge } from "@/components/ui/Badge";
import { useCaseStore } from "@/stores/case-store";

export default function Stage6Page() {
  const packagingRequestId = useCaseStore((s) => s.packagingRequestId);
  const lineId = useCaseStore((s) => s.lineId);
  const setOptimizationRunId = useCaseStore((s) => s.setOptimizationRunId);
  const setRecipeId = useCaseStore((s) => s.setRecipeId);

  const [run, setRun] = useState<OptimizationRunOut | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!packagingRequestId || !lineId || run) return;
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
  }, [packagingRequestId, lineId]);

  const eliminatedCount = run ? run.generated_candidate_count - run.survived_constraint_engine_count : 0;

  return (
    <div>
      <StageHeader
        no={6}
        title="Optimizasyon (Ana Motor)"
        description="Virgin/PCR/regranül oranları, katman dağılımları ve mikron/gramaj kombinasyonları üretilir; her aday teknik performans, üretilebilirlik, mevzuat, kaynak kullanımı, karbon, fire ve maliyet açısından değerlendirilir."
      />

      {(!packagingRequestId || !lineId) && (
        <Card className="border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">Önce Aşama 2-5&apos;i tamamlamalısınız.</p>
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
          <div className="mb-6 grid grid-cols-3 gap-4">
            <StatTile label="Üretilen Aday" value={run.generated_candidate_count} />
            <StatTile label="Kısıt Motorundan Geçen" value={run.survived_constraint_engine_count} />
            <StatTile label="Elenen" value={eliminatedCount} tone={eliminatedCount > 0 ? "warn" : "default"} />
          </div>

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
                    <p className="mt-1 text-sm text-ink/70">{e.summary_text}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>

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
        </>
      )}

      <StageNav currentNo={6} nextEnabled={!!run} />
    </div>
  );
}
