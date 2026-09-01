"use client";

import { useParams } from "next/navigation";
import { DigitalTwinView } from "@/components/digital-twin/DigitalTwinView";

/** Faz O.1 (Madde 18) — Ambalajın Dijital İkizi'nin genel web sayfası.
 * DPP sayfası gibi `(flow)` rota grubunun DIŞINDA, case-store'a bağımlı
 * değil — sadece URL'deki reçete numarasından bağımsız çalışır. */
export default function DigitalTwinPage() {
  const params = useParams<{ recipeId: string }>();
  const recipeId = params.recipeId;

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <p className="font-heading text-sm uppercase tracking-wide text-ink/50">Reçete OS — Ambalajın Dijital İkizi</p>
      <h1 className="mt-1 font-heading text-2xl font-semibold text-ink">
        Reçete, Makine, Proses, Test, Enerji/Karbon/Fire ve Mevzuatın Birleşik Görünümü
      </h1>
      <p className="mt-2 text-sm text-ink/60">
        Bu görünüm her açılışta DB&apos;nin güncel halinden taze derlenir — statik bir anlık görüntü değildir.
      </p>
      <div className="mt-6">
        <DigitalTwinView recipeId={recipeId} />
      </div>
    </div>
  );
}
