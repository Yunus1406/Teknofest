"use client";

/** Faz M.2 (Madde 12) — aday sayılarının (üretilen → teknik olarak mümkün →
 * finalist) huni (funnel) görselleştirmesi. Bu projede hiçbir grafik
 * kütüphanesi yok (bkz. LayeredCompositionBar) — CSS-tabanlı, orantılı
 * genişlikte daralan barlar. Kimlik hiçbir zaman yalnızca genişlikle
 * taşınmaz — her bar kendi etiketini ve sayısını taşır. */

const TONE_BG: Record<string, string> = {
  petrol: "bg-petrol",
  virgin: "bg-virgin",
  warn: "bg-warn",
  pcr: "bg-pcr",
};

export interface FunnelStage {
  label: string;
  value: number;
  tone?: "petrol" | "virgin" | "warn" | "pcr";
}

export function FunnelChart({ stages }: { stages: FunnelStage[] }) {
  const max = Math.max(...stages.map((s) => s.value), 1);

  return (
    <div
      className="space-y-2"
      role="img"
      aria-label={`Huni: ${stages.map((s) => `${s.label} ${s.value}`).join(" → ")}`}
    >
      {stages.map((stage, i) => {
        const widthPct = stage.value > 0 ? Math.max((stage.value / max) * 100, 6) : 0;
        return (
          <div key={i} className="flex items-center gap-3">
            <div className="w-44 shrink-0 text-right text-xs text-ink/60">{stage.label}</div>
            <div className="flex-1">
              {stage.value > 0 ? (
                <div
                  className={`mx-auto flex h-9 items-center justify-center rounded-md transition-all ${TONE_BG[stage.tone ?? "petrol"]}`}
                  style={{ width: `${widthPct}%` }}
                >
                  <span className="px-2 font-mono text-xs font-semibold text-white drop-shadow-sm">
                    {stage.value}
                  </span>
                </div>
              ) : (
                <div className="mx-auto flex h-9 w-full items-center justify-center rounded-md border border-dashed border-warn/40 bg-warn/5">
                  <span className="font-mono text-xs font-semibold text-warn">0</span>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
