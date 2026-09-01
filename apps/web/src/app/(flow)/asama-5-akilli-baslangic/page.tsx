"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { MaterialOut, RecipeOut } from "@/lib/types";
import { ActiveCaseSummary } from "@/components/layout/ActiveCaseSummary";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { LayerBreakdownTable } from "@/components/visualizations/LayerBreakdownTable";
import { LayeredCompositionBar } from "@/components/visualizations/LayeredCompositionBar";
import { recipeLayersToSegments, recipeLayersToTable } from "@/lib/composition-segments";
import { recipeSourceLabel, referenceSearchTierLabel } from "@/lib/labels";
import { useCaseStore } from "@/stores/case-store";

export default function Stage5Page() {
  const packagingRequestId = useCaseStore((s) => s.packagingRequestId);
  const lineId = useCaseStore((s) => s.lineId);
  const lineEligible = useCaseStore((s) => s.lineEligible);
  const setRecipeId = useCaseStore((s) => s.setRecipeId);

  const [recipe, setRecipe] = useState<RecipeOut | null>(null);
  const [materials, setMaterials] = useState<MaterialOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Faz K.8 (Madde 10) — `lineId` var ama `lineEligible=false` olabilir
    // (ör. kullanıcı Aşama 4'te uyumsuz yeni bir hat oluşturdu); bu durumda
    // Akıllı Başlangıç HİÇ tetiklenmemeli, aşağıdaki gate mesajı gösterilir.
    if (!packagingRequestId || !lineId || !lineEligible) return;
    Promise.all([api.generateInitialRecipe(packagingRequestId, lineId), api.listMaterials()])
      .then(([r, mats]) => {
        setRecipe(r);
        setMaterials(mats);
        setRecipeId(r.id);
      })
      .catch((e) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [packagingRequestId, lineId, lineEligible]);

  const materialById = Object.fromEntries(materials.map((m) => [m.id, m]));

  return (
    <div>
      <StageHeader
        no={5}
        title="Mevcut Reçete / Akıllı Başlangıç"
        description="Geçmiş doğrulanmış reçete varsa referans alınır; yoksa hammadde, hat ve mevzuat sınırlarına göre güvenli bir başlangıç reçetesi üretilir. Onayınızla optimizasyona geçilir."
      />
      <ActiveCaseSummary />

      {(!packagingRequestId || !lineId) && (
        <Card className="border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">Önce Aşama 2-4&apos;ü tamamlamalısınız.</p>
        </Card>
      )}
      {packagingRequestId && lineId && !lineEligible && (
        <Card className="border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">
            ⛔ Akıllı Başlangıç başlatılamıyor. Seçili üretim hattı bu ambalaj talebiyle uyumlu değil — Aşama
            4&apos;e dönüp uyumlu bir hat seçin.
          </p>
        </Card>
      )}
      {error && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      {recipe && (
        <Card>
          <div className="flex items-center justify-between">
            <CardTitle subtitle={`V${recipe.version} · ${recipe.layers.length} katman satırı`}>
              Başlangıç Reçetesi
            </CardTitle>
            <Badge tone={recipe.source === "referans_receteden" ? "pcr" : "petrol"}>
              {recipeSourceLabel(recipe.source)}
            </Badge>
          </div>
          <LayeredCompositionBar
            segments={recipeLayersToSegments(
              recipe.layers,
              (id) => materialById[id]?.material_type ?? "virgin",
              (id) => materialById[id]?.name ?? id
            )}
            heightClassName="h-14"
          />
          <LayerBreakdownTable
            groups={recipeLayersToTable(
              recipe.layers,
              (id) => materialById[id]?.material_type ?? "virgin",
              (id) => materialById[id]?.name ?? id
            )}
          />
          {recipe.reference_search_evidence ? (
            <div className="mt-4 rounded-lg bg-petrol/5 p-3">
              <p className="text-sm font-medium text-ink">
                Karar Dayanağı: {recipe.reference_search_evidence.evidence_count} doğrulanmış benzer üretim
              </p>
              <p className="mt-1 text-xs text-ink/60">
                Eşleşme kademesi: {referenceSearchTierLabel(recipe.reference_search_evidence.tier)} — bu reçete, firma
                hafızasındaki {recipe.reference_search_evidence.evidence_count} doğrulanmış geçmiş üretimden en
                yenisi referans alınarak oluşturuldu.
              </p>
            </div>
          ) : (
            <p className="mt-4 text-xs text-ink/50">
              Firma hafızasında doğrulanmış benzer reçete bulunamadı — bilgi tabanı + hat kısıtlarına göre tamamen
              virgin bir başlangıç reçetesi üretildi. Aşama 6&apos;da optimizasyon bu reçeteyi geliştirecek.
            </p>
          )}
        </Card>
      )}

      <StageNav currentNo={5} nextEnabled={!!recipe} />
    </div>
  );
}
