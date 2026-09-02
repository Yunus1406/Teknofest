"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { LifecycleEventOut } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { lifecycleEventLabel, lifecycleEventTone } from "@/lib/labels";

function eventDetailText(event: LifecycleEventOut): string | null {
  const d = event.detay;
  switch (event.event_type) {
    case "sartname_olusturuldu":
      return typeof d.packaging_type === "string" ? `${d.packaging_type} — ${d.product ?? ""}` : null;
    case "optimizasyon_calistirildi":
      return typeof d.generated_candidate_count === "number" ? `${d.generated_candidate_count} aday üretildi` : null;
    case "recete_uretildi":
    case "recete_revize_edildi":
      if (d.outcome === "basarisiz" && typeof d.basarisizlik_nedeni === "string") return d.basarisizlik_nedeni;
      if (Array.isArray(d.diff_from_previous) && d.diff_from_previous.length > 0)
        return `${d.diff_from_previous.length} kompozisyon değişikliği`;
      return null;
    case "pilot_uretim":
      return typeof d.status === "string" ? `Durum: ${d.status}` : null;
    case "fiziksel_test": {
      const basarili = d.basarili ?? 0;
      const basarisiz = d.basarisiz ?? 0;
      const beklemede = d.beklemede ?? 0;
      return `${basarili} geçti / ${basarisiz} kaldı / ${beklemede} beklemede`;
    }
    case "mevzuat_guncellendi":
      return typeof d.degisiklik_ozeti === "string" ? d.degisiklik_ozeti : null;
    default:
      return null;
  }
}

/** Faz R.1 (Madde 26) — Ambalaj Yaşam Döngüsü Zaman Çizelgesi. Mevcut olay
 * kaynaklarından türetilen, gerçek zaman damgalı bir birleşik görünüm
 * (bkz. apps/api/app/services/lifecycle_service.py). Her mount'ta TAZE
 * fetch edilir. */
export function LifecycleTimeline({ recipeId }: { recipeId: string }) {
  const [events, setEvents] = useState<LifecycleEventOut[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .getLifecycleTimeline(recipeId)
      .then(setEvents)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [recipeId]);

  if (loading) return <p className="text-sm text-ink/60">Yaşam döngüsü yükleniyor…</p>;
  if (error || !events) return <p className="text-sm text-warn">{error ?? "Yaşam döngüsü yüklenemedi."}</p>;
  if (events.length === 0) return <p className="text-sm text-ink/50">Bu reçete için henüz bir olay kaydı yok.</p>;

  return (
    <ol className="space-y-3">
      {events.map((e, i) => {
        const detail = eventDetailText(e);
        return (
          <li key={i} className="flex gap-3">
            <div className="mt-1 h-2 w-2 flex-shrink-0 rounded-full bg-petrol/40" />
            <div className="flex-1 border-b border-ink/10 pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={lifecycleEventTone(e.event_type)}>{lifecycleEventLabel(e.event_type)}</Badge>
                <span className="font-mono text-xs text-ink/40">
                  {new Date(e.tarih).toLocaleString("tr-TR")}
                </span>
              </div>
              <p className="mt-1 text-sm text-ink/70">{e.baslik}</p>
              {detail && <p className="mt-0.5 text-xs text-ink/50">{detail}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
