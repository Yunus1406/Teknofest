"use client";

import { useState } from "react";
import type { RiskScoreOut } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { riskComponentLabel, riskLevelLabel, riskLevelTone } from "@/lib/labels";

function formatDeger(v: number | string[] | null): string {
  if (v == null) return "—";
  if (Array.isArray(v)) return v.join(", ") || "—";
  return String(v);
}

/** Faz Q.1 (Madde 23) — Üretim Öncesi Risk Skoru. Şeffaf: hangi bileşenin
 * riski yükselttiği her zaman görünür (bkz. apps/api/app/services/
 * risk_service.py) — kara kutu bir skor DEĞİL. */
export function RiskScoreBadge({ risk }: { risk: RiskScoreOut }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      <button
        type="button"
        className="flex items-center gap-2"
        onClick={() => setExpanded((s) => !s)}
      >
        <Badge tone={riskLevelTone(risk.genel_risk)}>{riskLevelLabel(risk.genel_risk)}</Badge>
        <span className="text-xs text-petrol underline underline-offset-2">
          {expanded ? "Bileşenleri gizle" : "Neden? — Bileşenleri göster"}
        </span>
      </button>
      {expanded && (
        <ul className="mt-2 space-y-1.5">
          {Object.entries(risk.bilesenler).map(([key, c]) => (
            <li key={key} className="flex flex-wrap items-center gap-2 text-xs">
              <Badge tone={riskLevelTone(c.risk_katkisi)}>{riskComponentLabel(key)}</Badge>
              <span className="text-ink/60">{c.aciklama}</span>
              {c.deger != null && !Array.isArray(c.deger) && (
                <span className="font-mono text-ink/40">({formatDeger(c.deger)})</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
