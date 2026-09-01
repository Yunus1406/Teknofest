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
import { carbonEfStatusLabel, carbonEfStatusTone, dataConfidenceFromSourceKind, dataConfidenceTone } from "@/lib/labels";
import { useCaseStore } from "@/stores/case-store";

// Faz H.1 — Aşama 8'in HİÇBİR sayısı "gerçekleşen" ile karıştırılamaz;
// kart üstündeki tek rozetin yanında her sayının kendi yanında da görünür
// bir "Tahmini" etiketi taşınır (üretim + fiziksel doğrulama tamamlanmadan
// bu sayılar Aşama 12'de "Gerçekleşen" olarak DEĞİŞİR, burada değil).
function EstimateTag({ show }: { show: boolean }) {
  if (!show) return null;
  return <span className="ml-1 rounded bg-virgin/10 px-1 py-0.5 text-[9px] font-sans font-medium text-virgin">Tahmini</span>;
}

const TONE_DOT: Record<string, string> = {
  petrol: "bg-petrol", virgin: "bg-virgin", pcr: "bg-pcr", regranul: "bg-regranul", warn: "bg-warn", neutral: "bg-ink/40",
};

// Faz I.4 — H.5'in kaynak etiketinden türetilen "Veri Güveni"; küçük bir
// renkli nokta olarak gösterilir (yoğun 3 sütunlu grid'de her satıra tam
// bir rozet sığdırmak yerine), üzerine gelince (title) tam etiketi gösterir.
function ConfidenceDot({ sourceKind }: { sourceKind: string | null }) {
  const level = dataConfidenceFromSourceKind(sourceKind);
  if (!level) return null;
  const tone = dataConfidenceTone(level);
  const label = { yuksek: "Yüksek", orta: "Orta", dusuk: "Düşük", varsayimsal: "Varsayımsal" }[level] ?? level;
  return (
    <span
      className={`ml-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full ${TONE_DOT[tone]}`}
      title={`Veri Güveni: ${label}`}
    />
  );
}

function StatRow({
  label, value, estimated, confidenceKind = "hesaplanan",
}: {
  label: string; value: string | null; estimated: boolean; confidenceKind?: string | null;
}) {
  if (value === null) return null;
  return (
    <div>
      <dt className="text-ink/40">{label}</dt>
      <dd className="flex items-center">
        {value}
        <EstimateTag show={estimated} />
        <ConfidenceDot sourceKind={confidenceKind} />
      </dd>
    </div>
  );
}

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
        <StatRow label="Kalınlık" value={`${side.total_micron.toFixed(0)} µm`} estimated={side.is_estimated} />
        <StatRow label="Maliyet" value={`${side.cost_per_kg.toFixed(1)} TL/kg`} estimated={side.is_estimated} />
        <StatRow
          label="Karbon"
          value={`${side.carbon_kg_co2_per_kg.toFixed(2)} kg CO₂/kg`}
          estimated={side.is_estimated}
          confidenceKind={side.carbon_data_quality}
        />
        <StatRow
          label="Virgin (1000 birim)"
          value={side.virgin_kg !== null ? `${side.virgin_kg.toFixed(2)} kg` : null}
          estimated={side.is_estimated}
        />
        <StatRow
          label="PCR (1000 birim)"
          value={side.pcr_kg !== null ? `${side.pcr_kg.toFixed(2)} kg` : null}
          estimated={side.is_estimated}
        />
        <StatRow
          label="PIR-Regranül (1000 birim)"
          value={side.regranul_kg !== null ? `${side.regranul_kg.toFixed(2)} kg` : null}
          estimated={side.is_estimated}
        />
        <StatRow
          label="Fire (1000 birim)"
          value={side.fire_kg !== null ? `${side.fire_kg.toFixed(2)} kg` : null}
          estimated={side.is_estimated}
        />
        <StatRow
          label="Enerji (1000 birim)"
          value={side.enerji_kwh !== null ? `${side.enerji_kwh.toFixed(2)} kWh` : null}
          estimated={side.is_estimated}
        />
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
