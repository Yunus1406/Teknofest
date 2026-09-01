"use client";

import { useState } from "react";
import type { EliminatedCandidateOut } from "@/lib/types";

/** Faz P.3 (Madde 22) — "Neden Bu Reçeteyi Seçtin?" madde madde açıklama +
 * "Neden diğerleri seçilmedi?" (bkz. apps/api/app/services/
 * explainability_service.py). Her madde gerçek bir hesaplanmış değere
 * bağlıdır; boş liste normaldir (yeterli veri yoksa madde üretilmez). */
export function FinalistExplanation({
  bullets,
  eliminated = [],
}: {
  bullets: string[];
  eliminated?: EliminatedCandidateOut[];
}) {
  const [showEliminated, setShowEliminated] = useState(false);

  if (bullets.length === 0 && eliminated.length === 0) return null;

  return (
    <div className="mt-4 space-y-3">
      {bullets.length > 0 && (
        <div className="rounded-lg bg-petrol/5 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-petrol/70">Neden Bu Reçeteyi Seçtin?</p>
          <ul className="mt-1.5 space-y-1">
            {bullets.map((b, i) => (
              <li key={i} className="flex gap-2 text-sm text-ink/80">
                <span className="text-petrol">✓</span>
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {eliminated.length > 0 && (
        <div>
          <button
            type="button"
            className="text-sm font-medium text-petrol underline underline-offset-2"
            onClick={() => setShowEliminated((s) => !s)}
          >
            {showEliminated ? "Elenen reçeteleri gizle" : "Neden Diğerleri Seçilmedi? — Elenen reçeteleri göster"}
          </button>
          {showEliminated && (
            <ul className="mt-3 space-y-2">
              {eliminated.map((e, i) => (
                <li key={i} className="rounded-lg bg-warn/5 p-3 text-sm">
                  <p className="font-mono text-xs text-ink/50">{e.composition_summary}</p>
                  <p className="mt-1 text-ink/70">{e.summary_text}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
