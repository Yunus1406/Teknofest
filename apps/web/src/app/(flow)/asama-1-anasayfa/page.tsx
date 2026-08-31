"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import type { DashboardSummaryOut } from "@/lib/types";
import { StageHeader } from "@/components/layout/StageHeader";
import { Card, CardTitle } from "@/components/ui/Card";
import { StatTile } from "@/components/ui/StatTile";
import { Button } from "@/components/ui/Button";
import { LayeredCompositionBar } from "@/components/visualizations/LayeredCompositionBar";
import { aggregateToSegments } from "@/lib/composition-segments";
import { useCaseStore } from "@/stores/case-store";

export default function Stage1Page() {
  const [summary, setSummary] = useState<DashboardSummaryOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reset = useCaseStore((s) => s.reset);

  useEffect(() => {
    api
      .getDashboardSummary()
      .then(setSummary)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div>
      <StageHeader
        no={1}
        title="Ana Ekran"
        description="Firmanın genel sürdürülebilirlik durumu: aktif çalışmalar, doğrulanmış reçeteler, toplam hammadde kullanımı, gerçekleşen fire ve (varsa) karbon azaltımı."
      />

      {error && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">
            Backend&apos;e ulaşılamadı: {error}. API&apos;nin çalıştığından emin olun (bkz. README —{" "}
            <code className="font-mono">uvicorn app.main:app</code>).
          </p>
        </Card>
      )}

      <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="Aktif Çalışmalar" value={summary?.active_cases ?? "—"} />
        <StatTile label="Tamamlanan Çalışmalar" value={summary?.completed_cases ?? "—"} />
        <StatTile label="Doğrulanmış Reçeteler" value={summary?.verified_recipes ?? "—"} />
        <StatTile
          label="Mevzuat Uyarıları"
          value={summary?.regulatory_alerts ?? "—"}
          tone={summary && summary.regulatory_alerts > 0 ? "warn" : "default"}
        />
      </div>

      <Card className="mb-6">
        <CardTitle subtitle="Yalnızca üretime alınmış (ProductionOrder açılmış) reçetelerin gerçek kütlesi; her vaka bir kez sayılır.">
          Toplam Virgin / PCR / PIR-Regranül Kullanımı
        </CardTitle>
        {summary ? (
          summary.total_virgin_kg + summary.total_pcr_kg + summary.total_regranule_kg > 0 ? (
            <>
              <LayeredCompositionBar
                segments={aggregateToSegments(
                  summary.total_virgin_pct,
                  summary.total_pcr_pct,
                  summary.total_regranule_pct
                )}
                heightClassName="h-12"
              />
              <dl className="mt-3 grid grid-cols-3 gap-3 font-mono text-xs text-ink/60">
                <div>
                  <dt className="text-ink/40">Virgin</dt>
                  <dd>
                    {summary.total_virgin_kg.toFixed(1)} kg (%{summary.total_virgin_pct.toFixed(0)})
                  </dd>
                </div>
                <div>
                  <dt className="text-ink/40">PCR</dt>
                  <dd>
                    {summary.total_pcr_kg.toFixed(1)} kg (%{summary.total_pcr_pct.toFixed(0)})
                  </dd>
                </div>
                <div>
                  <dt className="text-ink/40">PIR-Regranül</dt>
                  <dd>
                    {summary.total_regranule_kg.toFixed(1)} kg (%{summary.total_regranule_pct.toFixed(0)})
                  </dd>
                </div>
              </dl>
            </>
          ) : (
            <p className="text-sm text-ink/40">Henüz üretime alınmış bir reçete yok.</p>
          )
        ) : (
          <div className="h-12 animate-pulse rounded-md bg-ink/5" />
        )}
      </Card>

      <Card className="mb-8">
        <CardTitle>Sürdürülebilirlik Kazanımı</CardTitle>
        <dl className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-ink/50">Gerçekleşen Fire (toplam)</dt>
            <dd className="mt-1 font-heading text-xl font-semibold text-ink">
              {summary ? summary.realized_waste_kg.toFixed(1) : "—"}{" "}
              <span className="text-base font-normal text-ink/50">kg</span>
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-ink/50">
              Karbon Azaltımı (doğrulanmış referansa göre)
            </dt>
            <dd className="mt-1 font-heading text-xl font-semibold text-ink">
              {summary?.carbon_reduction_kg_co2 != null ? (
                <>
                  {summary.carbon_reduction_kg_co2.toFixed(1)} <span className="text-base font-normal text-ink/50">kg CO₂</span>
                </>
              ) : (
                <span className="text-base font-normal text-ink/40">
                  — Bu türde henüz karşılaştırılabilecek 2. bir doğrulanmış üretim yok
                </span>
              )}
            </dd>
          </div>
        </dl>
        {summary?.prevented_waste_kg != null && (
          <p className="mt-3 text-xs text-ink/50">
            Önlenen fire (bir önceki doğrulanmış üretime göre):{" "}
            <span className="font-mono text-ink/70">{summary.prevented_waste_kg.toFixed(1)} kg</span>
          </p>
        )}
      </Card>

      <div className="flex items-center gap-3">
        <Link href="/asama-2-ambalaj-tanimlama" onClick={() => reset()}>
          <Button>Yeni Ambalaj Talebi Başlat →</Button>
        </Link>
        <p className="text-xs text-ink/50">Sıfırdan bir ambalaj tanımlayıp 12 aşamalı akışı başlatır.</p>
      </div>
    </div>
  );
}
