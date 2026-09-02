"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api-client";
import type { ComplianceDossierOut } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { dossierDurumLabel, dossierDurumTone } from "@/lib/labels";

/** Faz R.2 (Madde 27) — Dijital Uygunluk Dosyası'nın genel web sayfası.
 * DPP sayfası/Dijital İkiz gibi `(flow)` rota grubunun DIŞINDA, case-store'a
 * bağımlı değil — sadece URL'deki SKU numarasından bağımsız çalışır. Her
 * açılışta DB'nin güncel halinden taze derlenir (bkz.
 * app/services/compliance_dossier_service.py). */
export default function ComplianceDossierPage() {
  const params = useParams<{ skuId: string }>();
  const skuId = params.skuId;

  const [dossier, setDossier] = useState<ComplianceDossierOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .getComplianceDossier(skuId)
      .then(setDossier)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [skuId]);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <p className="font-heading text-sm uppercase tracking-wide text-ink/50">Reçete OS — Dijital Uygunluk Dosyası</p>
      <h1 className="mt-1 font-heading text-2xl font-semibold text-ink">
        {dossier ? `${dossier.sku_code} — Uygunluk Durumu` : "Uygunluk Durumu"}
      </h1>
      <p className="mt-2 text-sm text-ink/60">
        Bu SKU&apos;nun ürün tanımından mevzuat sürüm geçmişine 11 kanıt kalemi tek ekranda — her kalem GERÇEK
        veriden türetilir, veri yoksa dürüstçe &quot;Eksik&quot; olarak işaretlenir.
      </p>
      <Link href="/urun-portfoyu" className="mt-2 inline-block text-sm text-petrol underline underline-offset-2">
        ← Ürün Portföyü&apos;ne Dön
      </Link>

      {loading && <p className="mt-6 text-sm text-ink/60">Yükleniyor…</p>}

      {error && (
        <Card className="mt-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      {!loading && dossier && (
        <>
          <CardTitle>
            <span className="mt-8 block">Kanıt Kalemleri</span>
          </CardTitle>
          <div className="space-y-3">
            {dossier.items.map((item) => (
              <Card key={item.key}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-heading text-base font-medium text-ink">{item.title}</span>
                  <Badge tone={dossierDurumTone(item.durum)}>{dossierDurumLabel(item.durum)}</Badge>
                </div>
                <p className="mt-1 text-sm text-ink/60">{item.aciklama}</p>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
