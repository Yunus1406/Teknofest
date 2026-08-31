"use client";

import { useState } from "react";
import type { CompositionSegment } from "@/lib/composition-segments";
import { formatPct, materialTypeLabel } from "@/lib/labels";

const FILL_CLASS: Record<CompositionSegment["materialType"], string> = {
  virgin: "bg-virgin",
  pcr: "bg-pcr",
  regranul: "bg-regranul",
};

// regranül tonu (mat gri) ile PCR yeşili, renk körlüğü açısından birbirine
// en yakın çift — güvenlik ağı olarak regranül bandına 45° dokulu bir
// desen ekleniyor (bkz. dataviz skill: "texture as backup channel").
const TEXTURE_STYLE: React.CSSProperties = {
  backgroundImage:
    "repeating-linear-gradient(45deg, rgba(19,34,30,0.16) 0px, rgba(19,34,30,0.16) 2px, transparent 2px, transparent 7px)",
};

/** İmza görsel öğe: virgin/PCR/regranül bileşimini gerçek bir ekstrüzyon
 * film kesitini andıran yatay katmanlı şerit olarak gösterir. Segmentler
 * arasında 2px yüzey rengi boşluk vardır; kimlik hiçbir zaman yalnızca
 * renkle taşınmaz — her segment altındaki lejant metinle eşleşir. */
export function LayeredCompositionBar({
  segments,
  heightClassName = "h-10",
  showLegend = true,
}: {
  segments: CompositionSegment[];
  heightClassName?: string;
  showLegend?: boolean;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const totals = segments.reduce(
    (acc, s) => {
      acc[s.materialType] = (acc[s.materialType] ?? 0) + s.widthPct;
      return acc;
    },
    {} as Record<CompositionSegment["materialType"], number>
  );

  return (
    <div>
      <div
        className={`flex w-full gap-[2px] overflow-hidden rounded-md bg-surface ${heightClassName}`}
        role="img"
        aria-label={`Kompozisyon: ${(["virgin", "pcr", "regranul"] as const)
          .map((t) => `${materialTypeLabel(t)} ${formatPct(totals[t] ?? 0)}`)
          .join(", ")}`}
      >
        {segments.map((seg) => {
          const isNarrow = seg.widthPct < 12;
          return (
            <div
              key={seg.key}
              className={`relative flex items-center justify-center transition-opacity ${FILL_CLASS[seg.materialType]} ${
                hovered && hovered !== seg.key ? "opacity-50" : "opacity-100"
              }`}
              style={{ width: `${seg.widthPct}%`, ...(seg.materialType === "regranul" ? TEXTURE_STYLE : {}) }}
              onMouseEnter={() => setHovered(seg.key)}
              onMouseLeave={() => setHovered(null)}
              title={`${seg.detail ?? seg.label} — ${formatPct(seg.widthPct)}`}
            >
              {!isNarrow && (
                <span className="px-1 font-mono text-[11px] font-medium text-white drop-shadow-sm">
                  {formatPct(seg.widthPct)}
                </span>
              )}
            </div>
          );
        })}
      </div>
      {showLegend && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink/70">
          {(["virgin", "pcr", "regranul"] as const).map((t) =>
            (totals[t] ?? 0) > 0.01 ? (
              <span key={t} className="inline-flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-sm ${FILL_CLASS[t]}`} aria-hidden />
                {materialTypeLabel(t)} · <span className="font-mono">{formatPct(totals[t] ?? 0)}</span>
              </span>
            ) : null
          )}
        </div>
      )}
    </div>
  );
}
