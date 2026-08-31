"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { MaterialOut, OptimizationRunOut } from "@/lib/types";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Meter } from "@/components/ui/Meter";
import { LayerBreakdownTable } from "@/components/visualizations/LayerBreakdownTable";
import { LayeredCompositionBar } from "@/components/visualizations/LayeredCompositionBar";
import { recipeLayersToSegments, recipeLayersToTable } from "@/lib/composition-segments";
import {
  carbonEfStatusLabel,
  carbonEfStatusTone,
  dataConfidenceLabel,
  dataConfidenceTone,
  dataSourceTagLabel,
  dataSourceTagTone,
  referenceSearchTierLabel,
  scoreCriterionLabel,
} from "@/lib/labels";
import { useCaseStore } from "@/stores/case-store";

export default function Stage7Page() {
  const optimizationRunId = useCaseStore((s) => s.optimizationRunId);
  const setRecipeId = useCaseStore((s) => s.setRecipeId);
  const recipeId = useCaseStore((s) => s.recipeId);

  const [run, setRun] = useState<OptimizationRunOut | null>(null);
  const [materials, setMaterials] = useState<MaterialOut[]>([]);
  const [showEliminated, setShowEliminated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!optimizationRunId) return;
    Promise.all([api.getOptimizationRun(optimizationRunId), api.listMaterials()])
      .then(([r, mats]) => {
        setRun(r);
        setMaterials(mats);
      })
      .catch((e) => setError(String(e)));
  }, [optimizationRunId]);

  const materialById = Object.fromEntries(materials.map((m) => [m.id, m]));

  return (
    <div>
      <StageHeader
        no={7}
        title="Reçete Önerileri"
        description="3-4 güçlü alternatif — her biri için 'Neden Bu Reçete?' gerekçesi ve 'Karar Dayanağı' gösterilir. Her veri noktasının kaynağı belirtilir."
      />

      {!optimizationRunId && (
        <Card className="border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">Önce Aşama 6&apos;da optimizasyonu çalıştırmalısınız.</p>
        </Card>
      )}
      {error && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      <div className="space-y-5">
        {run?.finalists.map((f) => {
          const tierEval = f.recipe.evaluations.find((e) => e.tier === "tahmini_fiziksel_performans");
          const isSelected = recipeId === f.recipe.id;
          return (
            <Card key={f.id} className={isSelected ? "ring-1 ring-petrol/40" : ""}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <Badge tone="petrol">#{f.rank}</Badge>
                    <span className="font-mono text-xs text-ink/40">V{f.recipe.version}</span>
                    <Badge tone={dataConfidenceTone(tierEval?.data_confidence ?? null)}>
                      {dataConfidenceLabel(tierEval?.data_confidence ?? null)}
                    </Badge>
                    <Badge tone={carbonEfStatusTone(f.carbon_data_quality)}>
                      {carbonEfStatusLabel(f.carbon_data_quality)}
                    </Badge>
                  </div>
                  <p className="mt-1 font-heading text-lg font-semibold text-ink">
                    Skor: <span className="font-mono">{f.score.toFixed(2)}</span>
                  </p>
                </div>
                <Button variant={isSelected ? "primary" : "secondary"} onClick={() => setRecipeId(f.recipe.id)}>
                  {isSelected ? "Seçildi ✓" : "Bu Reçeteyi Seç"}
                </Button>
              </div>

              <div className="mt-4">
                <LayeredCompositionBar
                  segments={recipeLayersToSegments(
                    f.recipe.layers,
                    (id) => materialById[id]?.material_type ?? "virgin",
                    (id) => materialById[id]?.name ?? id
                  )}
                />
                <LayerBreakdownTable
                  groups={recipeLayersToTable(
                    f.recipe.layers,
                    (id) => materialById[id]?.material_type ?? "virgin",
                    (id) => materialById[id]?.name ?? id
                  )}
                />
              </div>

              <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 md:grid-cols-3">
                {Object.entries(f.score_breakdown).map(([k, v]) => (
                  <Meter key={k} label={scoreCriterionLabel(k)} value={v} />
                ))}
              </div>

              <div className="mt-4 rounded-lg bg-petrol/5 p-3">
                <p className="text-xs font-medium uppercase tracking-wide text-petrol/70">Neden Bu Reçete?</p>
                <p className="mt-1 text-sm text-ink/80">{f.justification_text}</p>
              </div>

              {f.recipe.data_source_tags && f.recipe.data_source_tags.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {f.recipe.data_source_tags.map((tag) => (
                    <Badge key={tag} tone={dataSourceTagTone(tag)}>
                      {dataSourceTagLabel(tag)}
                    </Badge>
                  ))}
                </div>
              )}

              <div className="mt-3 rounded-lg bg-ink/[0.03] p-3">
                <p className="text-xs font-medium uppercase tracking-wide text-ink/50">Karar Dayanağı</p>
                <div className="mt-1.5 space-y-1 text-xs text-ink/60">
                  <p>
                    Geçmiş doğrulanmış üretim:{" "}
                    <span className="font-mono">
                      {f.decision_basis.gecmis_receteler.length > 0
                        ? `${f.decision_basis.gecmis_receteler.length} doğrulanmış benzer üretim (${referenceSearchTierLabel(f.decision_basis.gecmis_recete_kademe ?? "")})`
                        : "firma hafızasında doğrulanmış benzer reçete bulunamadı"}
                    </span>
                  </p>
                  <p>
                    Hat teknik sınırları:{" "}
                    <span className="font-mono">
                      {f.decision_basis.hat_parametreleri?.hat ?? "—"}
                      {f.decision_basis.hat_parametreleri?.katman_yapisi
                        ? ` · ${f.decision_basis.hat_parametreleri.katman_yapisi}`
                        : ""}
                      {f.decision_basis.hat_parametreleri?.mikron_araligi
                        ? ` · ${f.decision_basis.hat_parametreleri.mikron_araligi} μm`
                        : ""}
                    </span>
                  </p>
                  <p>
                    Hammadde teknik veri föyü sayısı:{" "}
                    <span className="font-mono">{f.decision_basis.hammadde_veri_foyu_sayisi}</span>
                  </p>
                  <p>
                    Mevzuat maddeleri:{" "}
                    <span className="font-mono">{f.decision_basis.mevzuat_maddeleri.join(", ") || "—"}</span>
                  </p>
                  <p>
                    Karbon EF versiyonu:{" "}
                    <span className="font-mono">{f.decision_basis.karbon_ef_versiyonu ?? "Belirtilmedi"}</span>
                  </p>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {run && run.notable_eliminated.length > 0 && (
        <div className="mt-6">
          <button
            className="text-sm font-medium text-petrol underline underline-offset-2"
            onClick={() => setShowEliminated((s) => !s)}
          >
            {showEliminated ? "Elenen reçeteleri gizle" : "Neden Elendi? — Elenen reçeteleri göster"}
          </button>
          {showEliminated && (
            <ul className="mt-3 space-y-2">
              {run.notable_eliminated.map((e, i) => (
                <li key={i} className="rounded-lg bg-warn/5 p-3 text-sm">
                  <p className="font-mono text-xs text-ink/50">{e.composition_summary}</p>
                  <p className="mt-1 text-ink/70">{e.summary_text}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <StageNav currentNo={7} nextEnabled={!!recipeId} />
    </div>
  );
}
