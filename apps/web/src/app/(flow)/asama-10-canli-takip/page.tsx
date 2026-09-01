"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api-client";
import type { ProductionLiveDataOut } from "@/lib/types";
import { ActiveCaseSummary } from "@/components/layout/ActiveCaseSummary";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { dataSourceLabel, dataSourceTone } from "@/lib/labels";
import { useCaseStore } from "@/stores/case-store";

export default function Stage10Page() {
  const productionOrderId = useCaseStore((s) => s.productionOrderId);
  const setProductionOrderId = useCaseStore((s) => s.setProductionOrderId);
  const [rows, setRows] = useState<ProductionLiveDataOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [staleOrder, setStaleOrder] = useState(false);

  useEffect(() => {
    if (!productionOrderId) return;
    api
      .simulateLiveData(productionOrderId)
      .then(setRows)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) {
          // Kayıtlı üretim emri backend'de artık yok (ör. veritabanı sıfırlandı
          // ya da bu ID başka bir case'den kalmış) -- sahipsiz ID'yi temizle,
          // kullanıcıyı Aşama 9'da yeniden onay vermeye yönlendir.
          setProductionOrderId(null);
          setStaleOrder(true);
          return;
        }
        setError(String(e));
      });
  }, [productionOrderId, setProductionOrderId]);

  const last = rows?.[rows.length - 1];

  return (
    <div>
      <StageHeader
        no={10}
        title="Canlı Üretim Takibi"
        description="Üretilen miktar, gerçek hammadde tüketimleri, hat hızı, enerji ve fire — dönemsel ve kümülatif olarak ayrı ayrı gösterilir."
      />
      <ActiveCaseSummary />

      {staleOrder && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">
            Kayıtlı üretim emri artık bulunamadı (silinmiş veya farklı bir çalışmadan kalma bir
            kayıt olabilir). Lütfen Aşama 9&apos;a dönüp üretimi yeniden onaylayın.
          </p>
          <Link href="/asama-9-uretime-aktarim">
            <Button className="mt-3" variant="secondary">
              ← Aşama 9&apos;a Dön
            </Button>
          </Link>
        </Card>
      )}
      {error && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      {rows && (
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <CardTitle
              subtitle={
                last?.source === "simulasyon_verisi"
                  ? "Bu fazda gerçek makine entegrasyonu yok; veriler simüle edilmiştir. Şema, üretim ortamında gerçek PLC/SCADA verisiyle doğrudan beslenecek şekilde tasarlandı."
                  : "Gerçek üretim hattından canlı olarak alınan veriler."
              }
            >
              Üretim Akışı ({rows.length} veri noktası)
            </CardTitle>
            {last && <Badge tone={dataSourceTone(last.source)}>{dataSourceLabel(last.source)}</Badge>}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-xs text-ink/40">
                  <th className="py-1.5 pr-4 font-medium">Zaman</th>
                  <th className="py-1.5 pr-4 font-medium">Kümülatif Üretim</th>
                  <th className="py-1.5 pr-4 font-medium">Dönem Üretimi</th>
                  <th className="py-1.5 pr-4 font-medium">Dönem Enerjisi</th>
                  <th className="py-1.5 pr-4 font-medium">Kümülatif Enerji</th>
                  <th className="py-1.5 pr-4 font-medium">Dönem Fire</th>
                  <th className="py-1.5 pr-4 font-medium">Kümülatif Fire</th>
                  <th className="py-1.5 pr-4 font-medium">Hat Hızı</th>
                  <th className="py-1.5 pr-4 font-medium">Kaynak</th>
                </tr>
              </thead>
              <tbody className="font-mono text-xs">
                {rows.map((r, i) => (
                  <tr key={i} className="border-t border-ink/5">
                    <td className="py-1.5 pr-4 text-ink/50">
                      {r.ts ? new Date(r.ts).toLocaleTimeString("tr-TR") : "—"}
                    </td>
                    <td className="py-1.5 pr-4">{r.produced_qty_units.toLocaleString("tr-TR")}</td>
                    <td className="py-1.5 pr-4 text-ink/60">+{r.period_produced_qty_units.toLocaleString("tr-TR")}</td>
                    <td className="py-1.5 pr-4 text-ink/60">+{r.energy_kwh} kWh</td>
                    <td className="py-1.5 pr-4">{r.cumulative_energy_kwh} kWh</td>
                    <td className="py-1.5 pr-4 text-ink/60">+{r.waste_kg} kg</td>
                    <td className="py-1.5 pr-4">{r.cumulative_waste_kg} kg</td>
                    <td className="py-1.5 pr-4">{r.line_speed_m_min} m/dk</td>
                    <td className="py-1.5 pr-4">
                      <Badge tone={dataSourceTone(r.source)}>{dataSourceLabel(r.source)}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <StageNav currentNo={10} nextEnabled={!!rows} />
    </div>
  );
}
