"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { PackagingRequestOut } from "@/lib/types";
import { useCaseStore } from "@/stores/case-store";

/** Faz K.2 — "Aktif Çalışma Özeti" şeridi. Ambalajın temel verileri
 * (Ürün, Malzeme/Tür, Kalınlık, Gramaj, Gıda Teması, Hedef Pazar, Üretim
 * Miktarı) TEK bir kaynaktan (PackagingRequest) okunur ve her aşama
 * sayfasında sabit görünür -- kullanıcı akış boyunca hangi çalışma üzerinde
 * olduğunu her zaman görür, hiçbir modül kendi varsayımıyla bu veriyi
 * gölgeleyemez (sadece görüntüler, veriyi kopyalamaz). */
export function ActiveCaseSummary() {
  const packagingRequestId = useCaseStore((s) => s.packagingRequestId);
  const [req, setReq] = useState<PackagingRequestOut | null>(null);

  useEffect(() => {
    if (!packagingRequestId) {
      setReq(null);
      return;
    }
    let cancelled = false;
    api.getPackagingRequest(packagingRequestId).then((r) => {
      if (!cancelled) setReq(r);
    }).catch(() => {
      if (!cancelled) setReq(null);
    });
    return () => {
      cancelled = true;
    };
  }, [packagingRequestId]);

  if (!packagingRequestId || !req) return null;

  const parts = [
    req.product || req.packaging_type,
    req.target_market || null,
    req.food_contact ? "Gıda Teması" : null,
    req.target_thickness_micron != null ? `${req.target_thickness_micron} µm` : null,
    req.target_volume_units ? `${req.target_volume_units.toLocaleString("tr-TR")} adet` : null,
  ].filter(Boolean);

  if (parts.length === 0) return null;

  return (
    <div className="mb-6 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-petrol/15 bg-petrol/5 px-3 py-2 font-mono text-xs text-petrol">
      <span className="font-sans font-medium uppercase tracking-wide text-petrol/60">Aktif Çalışma:</span>
      {parts.map((p, i) => (
        <span key={i} className="flex items-center gap-2">
          {i > 0 && <span className="text-petrol/30">|</span>}
          {p}
        </span>
      ))}
    </div>
  );
}
