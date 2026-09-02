"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { SupplierEvidenceRadarOut } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { supplierEvidenceSignalLabel } from "@/lib/labels";
import type { Tone } from "@/lib/labels";

function completenessTone(pct: number): Tone {
  if (pct >= 80) return "pcr";
  if (pct >= 40) return "virgin";
  return "warn";
}

/** Faz R.3 (Madde 28) — Tedarikçi ve Hammadde Risk Radarı. Şeffaf: hangi
 * kanıt sinyalinin eksik olduğu her zaman görünür (bkz. apps/api/app/
 * services/supplier_risk_service.py) — tek bir kara kutu yüzde DEĞİL. */
export function SupplierEvidenceBadge({ materialId }: { materialId: string }) {
  const [radar, setRadar] = useState<SupplierEvidenceRadarOut | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getSupplierEvidenceRadar(materialId)
      .then((r) => {
        if (!cancelled) setRadar(r);
      })
      .catch(() => {
        /* rozet opsiyonel — sessizce atla */
      });
    return () => {
      cancelled = true;
    };
  }, [materialId]);

  if (radar == null) return null;

  return (
    <div>
      <button type="button" className="flex items-center gap-2" onClick={() => setExpanded((s) => !s)}>
        <Badge tone={completenessTone(radar.tamlik_pct)}>Kanıt Tamlığı %{radar.tamlik_pct}</Badge>
        <span className="text-xs text-petrol underline underline-offset-2">
          {expanded ? "Sinyalleri gizle" : "Sinyalleri göster"}
        </span>
      </button>
      {expanded && (
        <ul className="mt-2 space-y-1.5">
          {Object.entries(radar.signals).map(([key, s]) => (
            <li key={key} className="flex flex-wrap items-center gap-2 text-xs">
              <Badge tone={s.mevcut ? "pcr" : "warn"}>{supplierEvidenceSignalLabel(key)}</Badge>
              <span className="text-ink/60">{s.aciklama}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
