"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { ConversionStoryStageOut } from "@/lib/types";

function fmtPct(v: unknown): string {
  return typeof v === "number" ? `%${v.toFixed(1)}` : "—";
}

function fmtNum(v: unknown, unit: string): string {
  return typeof v === "number" ? `${v.toFixed(0)}${unit}` : "—";
}

/** Faz S.2 (Madde 30) — her aşamanın `veri` şekli farklı (bkz.
 * app/services/story_service.py); burada sadece kısa bir özet metnine
 * çevrilir, hiçbir yeni hesaplama yapılmaz. */
function stageSummary(stage: ConversionStoryStageOut): string {
  const veri = stage.veri as Record<string, any>;
  switch (stage.key) {
    case "baslangic": {
      if (!veri.has_reference) return (veri.note as string) ?? "Doğrulanmış referans bulunmamaktadır.";
      const ref = veri.reference ?? {};
      return `Virgin ${fmtPct(ref.virgin_pct)}, PCR ${fmtPct(ref.pcr_pct)}, ${fmtNum(ref.total_micron, " µm")}`;
    }
    case "oneri": {
      const line = veri.line_name ? `, Hat: ${veri.line_name}` : "";
      return `V${veri.version} — ${fmtNum(veri.total_micron, " µm")}${line}`;
    }
    case "uretim": {
      const line = veri.line as { name?: string } | null;
      const orders = (veri.orders as unknown[]) ?? [];
      return `${line?.name ?? "—"} — ${orders.length} üretim emri`;
    }
    case "dogrulama": {
      const ozet = veri.ozet ?? {};
      return `${ozet.basarili ?? 0} başarılı / ${ozet.basarisiz ?? 0} başarısız / ${ozet.beklemede ?? 0} beklemede`;
    }
    case "sonuc":
      return (veri.narrative as string) ?? "—";
    case "mevzuat": {
      const items = (veri.items as { changed_since_assessment: boolean }[]) ?? [];
      if (items.length === 0) return "Mevzuat değerlendirmesi yok.";
      const degisen = items.filter((i) => i.changed_since_assessment).length;
      return `${items.length} mevzuat değerlendirmesi — ${degisen} güncel versiyondan farklı`;
    }
    default:
      return "—";
  }
}

/** Faz S.2 (Madde 30) — Bir Ambalajın Dönüşüm Hikâyesi: sabit 6 aşamalı
 * "önce→sonra" akışı, Faz A-R'de zaten hesaplanmış verilerden derlenir
 * (bkz. app/services/story_service.py). Yeni hesaplama YOK — sunum
 * katmanı. Her mount'ta TAZE fetch edilir. */
export function ConversionStoryCard({ recipeId }: { recipeId: string }) {
  const [story, setStory] = useState<{ stages: ConversionStoryStageOut[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .getConversionStory(recipeId)
      .then(setStory)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [recipeId]);

  if (loading) return <p className="text-sm text-ink/60">Dönüşüm hikâyesi yükleniyor…</p>;
  if (error || !story) return <p className="text-sm text-warn">{error ?? "Dönüşüm hikâyesi yüklenemedi."}</p>;

  return (
    <div className="flex flex-wrap gap-3">
      {story.stages.map((stage, i) => (
        <div key={stage.key} className="flex min-w-[150px] flex-1 items-start gap-2">
          <div className="flex flex-col items-center">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-petrol/10 text-xs font-semibold text-petrol">
              {i + 1}
            </div>
            {i < story.stages.length - 1 && <div className="mt-1 h-full w-px flex-1 bg-ink/10 sm:hidden" />}
          </div>
          <div className="pb-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">{stage.baslik}</p>
            <p className="mt-0.5 text-sm text-ink/70">{stageSummary(stage)}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
