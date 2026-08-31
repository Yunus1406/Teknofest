"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { ComparisonOut, CompositionSide } from "@/lib/types";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { StatTile } from "@/components/ui/StatTile";
import { LayerBreakdownTable } from "@/components/visualizations/LayerBreakdownTable";
import { LayeredCompositionBar } from "@/components/visualizations/LayeredCompositionBar";
import { aggregateToSegments, layerCompositionOutToTable } from "@/lib/composition-segments";
import { carbonEfStatusLabel, carbonEfStatusTone } from "@/lib/labels";
import { useCaseStore } from "@/stores/case-store";

function SideCard({ side }: { side: CompositionSide }) {
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <CardTitle>{side.label}</CardTitle>
        {side.is_estimated && <Badge tone="virgin">Tahmini</Badge>}
      </div>
      <LayeredCompositionBar segments={aggregateToSegments(side.virgin_pct, side.pcr_pct, side.regranule_pct)} />
      {side.layers.length > 0 && <LayerBreakdownTable groups={layerCompositionOutToTable(side.layers)} />}
      <dl className="mt-4 grid grid-cols-3 gap-3 font-mono text-xs">
        <div>
          <dt className="text-ink/40">Kalınlık</dt>
          <dd>{side.total_micron.toFixed(0)} µm</dd>
        </div>
        <div>
          <dt className="text-ink/40">Maliyet</dt>
          <dd>{side.cost_per_kg.toFixed(1)} TL/kg</dd>
        </div>
        <div>
          <dt className="text-ink/40">Karbon</dt>
          <dd>{side.carbon_kg_co2_per_kg.toFixed(2)} kg CO₂/kg</dd>
        </div>
      </dl>
      <div className="mt-3">
        <Badge tone={carbonEfStatusTone(side.carbon_data_quality)}>
          {carbonEfStatusLabel(side.carbon_data_quality)}
        </Badge>
      </div>
    </Card>
  );
}

export default function Stage8Page() {
  const recipeId = useCaseStore((s) => s.recipeId);
  const [comparison, setComparison] = useState<ComparisonOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!recipeId) return;
    api.getComparison(recipeId).then(setComparison).catch((e) => setError(String(e)));
  }, [recipeId]);

  return (
    <div>
      <StageHeader
        no={8}
        title="Mevcut ↔ Önerilen Karşılaştırması"
        description="Referans ve önerilen reçete yan yana — sonuçlar üretim henüz yapılmadığı için açıkça 'Tahmini' olarak işaretlenir."
      />

      {!recipeId && (
        <Card className="border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">Önce Aşama 7&apos;de bir reçete seçmelisiniz.</p>
        </Card>
      )}
      {error && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      {comparison && (
        <>
          {!comparison.reference && (
            <Card className="mb-6 border-petrol/20 bg-petrol/5">
              <p className="text-sm text-ink/70">
                Bu ambalaj türü için firma hafızasında doğrulanmış bir referans reçete henüz yok; kazanım
                yüzdeleri bu nedenle gösterilmiyor. İlk doğrulanmış reçete kaydedildiğinde (Aşama 12)
                gelecekteki karşılaştırmalar otomatik referans bulacak.
              </p>
            </Card>
          )}

          <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
            {comparison.reference ? (
              <SideCard side={comparison.reference} />
            ) : (
              <Card className="flex items-center justify-center text-sm text-ink/40">Referans yok</Card>
            )}
            <SideCard side={comparison.recommended} />
          </div>

          {comparison.reference && comparison.gains && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <StatTile label="Karbon Azaltımı (Tahmini)" value={comparison.gains.karbon_azaltimi_pct} unit="%" />
                <StatTile label="Maliyet Azaltımı (Tahmini)" value={comparison.gains.maliyet_azaltimi_pct} unit="%" />
              </div>
              <p className="mt-2 text-xs text-ink/40">
                Karbon azaltımı, her iki reçetenin karbon figürüne dayanır —{" "}
                {carbonEfStatusLabel(comparison.recommended.carbon_data_quality)}.
              </p>
            </>
          )}
        </>
      )}

      <StageNav currentNo={8} nextEnabled={!!comparison} />
    </div>
  );
}
