"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { PackagingRequestOut, ProductionLineOut, ProductionOrderSummaryOut, RecipeOut } from "@/lib/types";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { LayerBreakdownTable } from "@/components/visualizations/LayerBreakdownTable";
import { layerCompositionOutToTable } from "@/lib/composition-segments";
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
  const [approvedBy, setApprovedBy] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [summary, setSummary] = useState<ProductionOrderSummaryOut | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

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

  useEffect(() => {
    if (!productionOrderId) return;
    api.getProductionOrderSummary(productionOrderId).then(setSummary).catch((e) => setSummaryError(String(e)));
  }, [productionOrderId]);

  async function handleConfirm() {
    if (!recipeId || !approvedBy.trim()) return;
    setConfirming(true);
    setError(null);
    try {
      const order = await api.createProductionOrder(recipeId, qty, approvedBy.trim());
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
              disabled={!!productionOrderId}
            />
          </label>

          <label className="mt-4 block">
            <span className="mb-1 block text-xs font-medium text-ink/60">
              Onaylayan Operatör/Kullanıcı — üretim emri bu isim olmadan oluşturulamaz
            </span>
            <input
              type="text"
              className="w-full rounded-lg border border-ink/15 bg-white/70 px-3 py-2 text-sm"
              value={approvedBy}
              onChange={(e) => setApprovedBy(e.target.value)}
              placeholder="Ör. Ahmet Yıldız"
              disabled={!!productionOrderId}
            />
          </label>

          <div className="mt-5 flex items-center gap-3">
            <Button onClick={handleConfirm} disabled={confirming || !!productionOrderId || !approvedBy.trim()}>
              {productionOrderId ? "Üretim Onaylandı ✓" : confirming ? "Onaylanıyor…" : "Üretimi Onayla"}
            </Button>
            {productionOrderId && <Badge tone="pcr">Üretim emri oluşturuldu</Badge>}
          </div>
        </Card>
      )}

      {summaryError && (
        <Card className="mt-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{summaryError}</p>
        </Card>
      )}

      {summary && (
        <Card className="mt-6">
          <div className="mb-3 flex items-center gap-2">
            <CardTitle>Üretim Emri Talimatı</CardTitle>
            {summary.order_no && <Badge tone="petrol">{summary.order_no}</Badge>}
          </div>
          <dl className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
            <div>
              <dt className="text-ink/40">Reçete Kodu</dt>
              <dd className="font-mono">{summary.recipe_code}</dd>
            </div>
            <div>
              <dt className="text-ink/40">Toplam Kalınlık</dt>
              <dd className="font-mono">{summary.total_micron !== null ? `${summary.total_micron.toFixed(0)} µm` : "—"}</dd>
            </div>
            <div>
              <dt className="text-ink/40">Hedef Hat Hızı</dt>
              <dd className="font-mono">
                {summary.target_line_speed_m_min !== null ? `${summary.target_line_speed_m_min} m/dk` : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-ink/40">Onaylayan</dt>
              <dd className="font-medium">
                {summary.approved_by ?? "—"}
                {summary.approved_at && (
                  <span className="ml-1 font-mono text-xs text-ink/40">
                    ({new Date(summary.approved_at).toLocaleString("tr-TR")})
                  </span>
                )}
              </dd>
            </div>
          </dl>

          <p className="mt-4 text-xs font-medium uppercase tracking-wide text-ink/50">Katman Dağılımı ve Hammaddeler</p>
          <LayerBreakdownTable groups={layerCompositionOutToTable(summary.layers)} />

          {summary.additives.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-medium uppercase tracking-wide text-ink/50">Katkı Maddeleri</p>
              <div className="mt-1 flex flex-wrap gap-2">
                {summary.additives.map((a, i) => (
                  <Badge key={`${a.additive_id}-${i}`} tone="neutral">
                    {a.additive_name} · %{a.dosage_pct}
                    {a.layer_index !== null ? ` · Katman ${a.layer_index}` : ""}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <p className="mt-4 text-xs font-medium uppercase tracking-wide text-ink/50">
            Hedef Proses Parametreleri {summary.target_process_parameters.length === 0 && "(bu hat için öneri bulunamadı)"}
          </p>
          {summary.target_process_parameters.length > 0 && (
            <div className="mt-1 grid grid-cols-2 gap-3 font-mono text-xs md:grid-cols-3">
              {summary.target_process_parameters.map((p, i) => (
                <div key={i}>
                  <dt className="text-ink/40">{p.parameter_name}</dt>
                  <dd>
                    {p.typical_min ?? "—"}–{p.typical_max ?? "—"} {p.unit}
                  </dd>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <StageNav currentNo={9} nextEnabled={!!productionOrderId} />
    </div>
  );
}
