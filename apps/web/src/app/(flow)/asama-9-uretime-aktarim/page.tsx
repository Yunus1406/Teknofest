"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { PackagingRequestOut, ProductionLineOut, RecipeOut } from "@/lib/types";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useCaseStore } from "@/stores/case-store";

export default function Stage9Page() {
  const recipeId = useCaseStore((s) => s.recipeId);
  const packagingRequestId = useCaseStore((s) => s.packagingRequestId);
  const productionOrderId = useCaseStore((s) => s.productionOrderId);
  const setProductionOrderId = useCaseStore((s) => s.setProductionOrderId);

  const [recipe, setRecipe] = useState<RecipeOut | null>(null);
  const [request, setRequest] = useState<PackagingRequestOut | null>(null);
  const [line, setLine] = useState<ProductionLineOut | null>(null);
  const [qty, setQty] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!recipeId || !packagingRequestId) return;
    Promise.all([api.getRecipe(recipeId), api.getPackagingRequest(packagingRequestId), api.listProductionLines()])
      .then(([r, req, lines]) => {
        setRecipe(r);
        setRequest(req);
        setQty(req.target_volume_units);
        setLine(lines.find((l) => l.id === r.line_id) ?? null);
      })
      .catch((e) => setError(String(e)));
  }, [recipeId, packagingRequestId]);

  async function handleConfirm() {
    if (!recipeId) return;
    setConfirming(true);
    setError(null);
    try {
      const order = await api.createProductionOrder(recipeId, qty);
      setProductionOrderId(order.id);
    } catch (e) {
      setError(String(e));
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div>
      <StageHeader
        no={9}
        title="Üretime Aktarım"
        description="Sistem uygun hat/makineyi otomatik seçer; siz üretimi onaylarsınız."
      />

      {error && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      {recipe && request && (
        <Card>
          <CardTitle subtitle={`Reçete V${recipe.version} · ${request.packaging_type}`}>
            Üretim Emri Özeti
          </CardTitle>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-ink/40">Seçilen Hat</dt>
              <dd className="font-medium">{line?.name ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-ink/40">Katman Yapısı</dt>
              <dd className="font-mono">{line?.layer_structure ?? "—"}</dd>
            </div>
          </dl>
          <label className="mt-4 block">
            <span className="mb-1 block text-xs font-medium text-ink/60">Üretim Miktarı (adet)</span>
            <input
              type="number"
              className="w-full rounded-lg border border-ink/15 bg-white/70 px-3 py-2 text-sm"
              value={qty}
              onChange={(e) => setQty(Number(e.target.value))}
            />
          </label>

          <div className="mt-5 flex items-center gap-3">
            <Button onClick={handleConfirm} disabled={confirming || !!productionOrderId}>
              {productionOrderId ? "Üretim Onaylandı ✓" : confirming ? "Onaylanıyor…" : "Üretimi Onayla"}
            </Button>
            {productionOrderId && <Badge tone="pcr">Üretim emri oluşturuldu</Badge>}
          </div>
        </Card>
      )}

      <StageNav currentNo={9} nextEnabled={!!productionOrderId} />
    </div>
  );
}
