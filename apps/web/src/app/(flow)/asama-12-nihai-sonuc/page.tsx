"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import type { DigitalProductPassportOut, FinalResultOut } from "@/lib/types";
import { StageHeader } from "@/components/layout/StageHeader";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { StatTile } from "@/components/ui/StatTile";
import { carbonEfStatusLabel, carbonEfStatusTone } from "@/lib/labels";
import { useCaseStore } from "@/stores/case-store";

export default function Stage12Page() {
  const recipeId = useCaseStore((s) => s.recipeId);
  const reset = useCaseStore((s) => s.reset);

  const [result, setResult] = useState<FinalResultOut | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [passport, setPassport] = useState<DigitalProductPassportOut | null>(null);
  const [creatingPassport, setCreatingPassport] = useState(false);
  const [passportError, setPassportError] = useState<string | null>(null);

  const [downloadingReport, setDownloadingReport] = useState<"technical" | "executive" | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  async function handleFinalize() {
    if (!recipeId) return;
    setSaving(true);
    setError(null);
    try {
      const r = await api.finalizeResult(recipeId);
      setResult(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleCreatePassport() {
    if (!recipeId) return;
    setCreatingPassport(true);
    setPassportError(null);
    try {
      const p = await api.createOrGetPassport(recipeId);
      setPassport(p);
    } catch (e) {
      setPassportError(String(e));
    } finally {
      setCreatingPassport(false);
    }
  }

  async function handleDownloadReport(format: "technical" | "executive") {
    if (!recipeId) return;
    setDownloadingReport(format);
    setReportError(null);
    try {
      await api.downloadOptimizationReport(recipeId, format);
    } catch (e) {
      setReportError(String(e));
    } finally {
      setDownloadingReport(null);
    }
  }

  const p = result?.per_1000_units;

  return (
    <div>
      <StageHeader
        no={12}
        title="Nihai Sonuç ve Sürdürülebilirlik Kazanımı"
        description="Artık 'Gerçekleşen' sonuçlar (tahmini değil): 1.000 satılabilir ambalaj başına kaynak kullanımı, üretim performansı ve reçete izlenebilirlik geçmişi."
      />

      {error && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      {!result && (
        <Card>
          <CardTitle subtitle="Bu işlem reçeteyi doğrulanmış olarak işaretler ve sistem gelecekteki akıllı başlangıç önerilerinde bu reçeteyi referans alır.">
            Doğrulanmış Reçeteyi Firma Hafızasına Kaydet
          </CardTitle>
          <Button onClick={handleFinalize} disabled={saving || !recipeId}>
            {saving ? "Kaydediliyor…" : "Kaydet ve Nihai Sonucu Göster"}
          </Button>
        </Card>
      )}

      {result && p && (
        <>
          <Card className="mb-6 border-pcr/30 bg-pcr/5">
            <div className="flex items-center gap-2">
              <Badge tone="pcr">Gerçekleşen</Badge>
              <Badge tone={result.physical_tests_passed ? "pcr" : "warn"}>
                {result.physical_tests_passed ? "Fiziksel testler başarılı" : "Fiziksel test kaydı yok/başarısız"}
              </Badge>
            </div>
            <p className="mt-2 text-sm text-ink/70">
              Reçete firma hafızasına kaydedildi — sistem bundan sonra bu ambalaj türü için akıllı başlangıç
              önerilerinde bu reçeteyi referans alacak.
            </p>
          </Card>

          <CardTitle>1.000 Satılabilir Ambalaj Başına Kaynak Kullanımı</CardTitle>
          <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-3">
            <StatTile label="Virgin" value={p.virgin_kg ?? "—"} unit="kg" />
            <StatTile label="PCR" value={p.pcr_kg ?? "—"} unit="kg" />
            <StatTile label="PIR-Regranül" value={p.regranul_kg ?? "—"} unit="kg" />
            <StatTile label="Karbon" value={p.karbon_kg_co2 ?? "—"} unit="kg CO₂" />
            <StatTile label="Fire" value={p.fire_kg ?? "—"} unit="kg" />
            <StatTile label="Enerji" value={p.enerji_kwh ?? "—"} unit="kWh" />
          </div>
          {p.karbon_kg_co2 != null && (
            <div className="-mt-5 mb-8">
              <Badge tone={carbonEfStatusTone(p.karbon_veri_kalitesi as string)}>
                {carbonEfStatusLabel(p.karbon_veri_kalitesi as string)}
              </Badge>
            </div>
          )}

          <Card>
            <CardTitle>Reçete İzlenebilirlik Geçmişi</CardTitle>
            <ol className="space-y-2">
              {result.version_history.map((v) => (
                <li key={v.id} className="flex items-center gap-3 text-sm">
                  <span className="font-mono text-xs text-ink/40">
                    {new Date(v.created_at).toLocaleDateString("tr-TR")}
                  </span>
                  <Badge tone="petrol">V{v.version}</Badge>
                  <span className="text-ink/60">{v.status}</span>
                  {v.is_verified && <Badge tone="pcr">Doğrulandı</Badge>}
                </li>
              ))}
            </ol>
          </Card>

          {reportError && (
            <Card className="mt-6 border-warn/30 bg-warn/5">
              <p className="text-sm text-warn">{reportError}</p>
            </Card>
          )}

          <Card className="mt-6">
            <CardTitle subtitle="Aşama 2-12 arasında biriken tüm doğrulanmış veriden otomatik derlenir — ek bir bilgi girmenize gerek yok.">
              Optimizasyon Raporu
            </CardTitle>
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => handleDownloadReport("technical")} disabled={!!downloadingReport || !recipeId}>
                {downloadingReport === "technical" ? "Hazırlanıyor…" : "Teknik Rapor (16 Bölüm)"}
              </Button>
              <Button
                variant="secondary"
                onClick={() => handleDownloadReport("executive")}
                disabled={!!downloadingReport || !recipeId}
              >
                {downloadingReport === "executive" ? "Hazırlanıyor…" : "Yönetici Özeti"}
              </Button>
            </div>
          </Card>

          {passportError && (
            <Card className="mt-6 border-warn/30 bg-warn/5">
              <p className="text-sm text-warn">{passportError}</p>
            </Card>
          )}

          <Card className="mt-6">
            <CardTitle subtitle="Herkese açık, versiyonlanan bir dijital kimlik oluşturur — QR ile paylaşılabilir; ticari hammadde detayları sadece Yetkili Alan'da görünür.">
              Dijital Ürün Pasaportu
            </CardTitle>
            {!passport ? (
              <Button onClick={handleCreatePassport} disabled={creatingPassport || !recipeId}>
                {creatingPassport ? "Oluşturuluyor…" : "Dijital Ürün Pasaportu Oluştur"}
              </Button>
            ) : (
              <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={passport.qr_code_data_uri}
                  alt={`${passport.public.header.passport_no} QR kodu`}
                  className="h-32 w-32 rounded-lg border border-ink/10 bg-white p-2"
                />
                <div>
                  <div className="flex items-center gap-2">
                    <Badge tone="petrol">{passport.public.header.passport_no}</Badge>
                    <Badge tone="neutral">Rev.{passport.public.header.revision}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-ink/60">
                    Bu QR kodu okutulduğunda pasaportun genel web sayfası açılır.
                  </p>
                  <Link
                    href={`/dpp/${passport.public.header.passport_no}`}
                    target="_blank"
                    className="mt-2 inline-block text-sm font-medium text-petrol underline underline-offset-2"
                  >
                    Dijital Pasaportu Görüntüle
                  </Link>
                </div>
              </div>
            )}
          </Card>

          <div className="mt-8 flex items-center gap-3 border-t border-ink/10 pt-6">
            <Link href="/asama-1-anasayfa" onClick={() => reset()}>
              <Button>Ana Ekrana Dön</Button>
            </Link>
            <Link href="/asama-2-ambalaj-tanimlama" onClick={() => reset()}>
              <Button variant="secondary">Yeni Ambalaj Talebi Başlat</Button>
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
