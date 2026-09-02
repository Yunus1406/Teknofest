"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import type { DigitalProductPassportOut, EcoDesignSuggestionOut, FinalResultOut } from "@/lib/types";
import { ActiveCaseSummary } from "@/components/layout/ActiveCaseSummary";
import { StageHeader } from "@/components/layout/StageHeader";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { StatTile } from "@/components/ui/StatTile";
import { SustainabilityScorecard } from "@/components/scorecard/SustainabilityScorecard";
import { EcoDesignSuggestions } from "@/components/eco-design/EcoDesignSuggestions";
import { FinalistExplanation } from "@/components/explainability/FinalistExplanation";
import { LifecycleTimeline } from "@/components/lifecycle/LifecycleTimeline";
import { ConversionStoryCard } from "@/components/story/ConversionStoryCard";
import {
  carbonEfStatusLabel,
  carbonEfStatusTone,
  dataConfidenceFromSourceKind,
  dataConfidenceLabel,
  dataConfidenceTone,
  dataSourceLabel,
  dataSourceTone,
} from "@/lib/labels";
import { useCaseStore } from "@/stores/case-store";

// Faz H.4 — Referans | Tahmini | Gerçekleşen, üçü de 1.000 birim başına AYNI
// birimde (kg) — doğrudan kıyaslanabilir.
const TRIPLE_ROWS: { key: string; label: string; unit: string }[] = [
  { key: "virgin_kg", label: "Virgin", unit: "kg" },
  { key: "pcr_kg", label: "PCR", unit: "kg" },
  { key: "regranul_kg", label: "PIR-Regranül", unit: "kg" },
  { key: "karbon_kg_co2", label: "Karbon", unit: "kg CO₂" },
  { key: "fire_kg", label: "Fire", unit: "kg" },
  { key: "enerji_kwh", label: "Enerji", unit: "kWh" },
];

// Faz N.2 (Madde 15) — bu tek metrik için düşük değer İYİ değil, YÜKSEK
// değer iyidir; rozet rengi bu yüzden diğer iki metrikten TERS yönde
// değerlendirilir (bkz. apps/api/app/schemas/company.py
// COMPANY_BENCHMARK_METRICS).
const HIGHER_IS_BETTER_METRICS = new Set(["pcr_orani_pct"]);

const GAIN_LABELS: Record<string, string> = {
  karbon_azaltimi_pct: "Karbon Azaltımı",
  virgin_azaltimi_pct: "Virgin Azaltımı",
  fire_azaltimi_pct: "Fire Azaltımı",
  enerji_azaltimi_pct: "Enerji Azaltımı",
};

function formatTripleCell(v: number | string | null | undefined, unit: string): string {
  if (typeof v !== "number") return "—";
  return `${v.toFixed(2)} ${unit}`;
}

export default function Stage12Page() {
  const recipeId = useCaseStore((s) => s.recipeId);
  const reset = useCaseStore((s) => s.reset);

  const [result, setResult] = useState<FinalResultOut | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [ecoDesignSuggestions, setEcoDesignSuggestions] = useState<EcoDesignSuggestionOut[]>([]);

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
      // Faz P.2 (Madde 21) — sonucun gösterimini engellemesin diye ayrı try/catch.
      api
        .getEcoDesignSuggestions(recipeId)
        .then(setEcoDesignSuggestions)
        .catch(() => setEcoDesignSuggestions([]));
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
      <ActiveCaseSummary />

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

          <Card className="mb-8">
            <CardTitle subtitle="1.000 satılabilir ambalaj başına — üç sütun da AYNI birimde (kg), doğrudan kıyaslanabilir.">
              Referans | Tahmini | Gerçekleşen
            </CardTitle>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-ink/40">
                    <th className="py-1 pr-4 font-normal"></th>
                    <th className="py-1 pr-4 font-normal">
                      Referans
                      {(() => {
                        const level = dataConfidenceFromSourceKind("gecmis_uretim");
                        return level ? (
                          <span className="ml-1">
                            <Badge tone={dataConfidenceTone(level)}>{dataConfidenceLabel(level)}</Badge>
                          </span>
                        ) : null;
                      })()}
                    </th>
                    <th className="py-1 pr-4 font-normal">
                      Tahmini <Badge tone="virgin">Aşama 8</Badge>
                    </th>
                    <th className="py-1 pr-4 font-normal">
                      Gerçekleşen <Badge tone="pcr">Aşama 12</Badge>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {TRIPLE_ROWS.map((row) => (
                    <tr key={row.key} className="border-t border-ink/5">
                      <td className="py-1.5 pr-4 text-ink/50">{row.label}</td>
                      <td className="py-1.5 pr-4 font-mono">
                        {result.triple_comparison.reference ? (
                          formatTripleCell(result.triple_comparison.reference[row.key], row.unit)
                        ) : (
                          <span className="text-ink/30">Referans yok</span>
                        )}
                      </td>
                      <td className="py-1.5 pr-4 font-mono">
                        {formatTripleCell(result.triple_comparison.tahmini[row.key], row.unit)}
                      </td>
                      <td className="py-1.5 pr-4 font-mono">
                        {result.triple_comparison.gerceklesen
                          ? formatTripleCell(result.triple_comparison.gerceklesen[row.key], row.unit)
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {p.karbon_kg_co2 != null && (
              <div className="mt-3">
                <Badge tone={carbonEfStatusTone(p.karbon_veri_kalitesi as string)}>
                  {carbonEfStatusLabel(p.karbon_veri_kalitesi as string)}
                </Badge>
              </div>
            )}
            {result.triple_comparison.gains && (
              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(result.triple_comparison.gains).map(([k, v]) => (
                  <Badge key={k} tone={v >= 0 ? "pcr" : "warn"}>
                    {GAIN_LABELS[k] ?? k}: {v}%
                  </Badge>
                ))}
              </div>
            )}
            {!result.triple_comparison.reference && (
              <p className="mt-3 text-xs text-ink/40">
                Bu ambalaj türü için firma hafızasında doğrulanmış bir referans reçete henüz yok; azaltım
                yüzdeleri bu nedenle gösterilmiyor.
              </p>
            )}
          </Card>

          <CardTitle>1.000 Satılabilir Ambalaj Başına Kaynak Kullanımı (Gerçekleşen Ayrıntı)</CardTitle>
          {/* Faz H.3 — Virgin/PCR/Regranül/Karbon reçete kompozisyonundan
              HESAPLANIR; Fire/Enerji GERÇEKTEN canlı üretim verisinden gelir
              (bugün her zaman simülasyon, gerçek PLC/SCADA yok) — tek bir
              "Gerçekleşen" etiketi altında ASLA karıştırılmaz, her grup
              kendi kaynak rozetini taşır. */}
          <div className="mb-4">
            <div className="mb-2 flex items-center gap-2">
              {p.kutle_veri_kaynagi != null && typeof p.kutle_veri_kaynagi === "string" && (
                <>
                  <Badge tone={dataSourceTone(p.kutle_veri_kaynagi)}>{dataSourceLabel(p.kutle_veri_kaynagi)}</Badge>
                  {(() => {
                    const level = dataConfidenceFromSourceKind(p.kutle_veri_kaynagi as string);
                    return level ? (
                      <Badge tone={dataConfidenceTone(level)}>{dataConfidenceLabel(level)}</Badge>
                    ) : null;
                  })()}
                </>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <StatTile label="Virgin" value={p.virgin_kg ?? "—"} unit="kg" />
              <StatTile label="PCR" value={p.pcr_kg ?? "—"} unit="kg" />
              <StatTile label="PIR-Regranül" value={p.regranul_kg ?? "—"} unit="kg" />
              <StatTile label="Karbon" value={p.karbon_kg_co2 ?? "—"} unit="kg CO₂" />
            </div>
          </div>
          <div className="mb-8">
            <div className="mb-2 flex items-center gap-2">
              {p.fire_enerji_veri_kaynagi != null && typeof p.fire_enerji_veri_kaynagi === "string" && (
                <>
                  <Badge tone={dataSourceTone(p.fire_enerji_veri_kaynagi)}>{dataSourceLabel(p.fire_enerji_veri_kaynagi)}</Badge>
                  {(() => {
                    const level = dataConfidenceFromSourceKind(p.fire_enerji_veri_kaynagi as string);
                    return level ? (
                      <Badge tone={dataConfidenceTone(level)}>{dataConfidenceLabel(level)}</Badge>
                    ) : null;
                  })()}
                </>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
              <StatTile label="Fire" value={p.fire_kg ?? "—"} unit="kg" />
              <StatTile label="Enerji" value={p.enerji_kwh ?? "—"} unit="kWh" />
            </div>
          </div>

          <Card className="mb-8">
            <CardTitle>Sektöre Göre Konum (Benchmark Karşılaştırması)</CardTitle>
            {!result.benchmark_karsilastirmasi.available ? (
              <p className="text-sm text-ink/50">
                Benchmark: Veri Yok —{" "}
                <Link href="/firma-profili" className="text-petrol underline underline-offset-2">
                  Firma Profili
                </Link>
                &apos;nden kendi geçmiş üretim ortalamanızı ya da doğrulanmış bir sektör kaynağını girerek bu
                karşılaştırmayı etkinleştirebilirsiniz.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-ink/50">
                    <th className="pb-2 font-medium">Metrik</th>
                    <th className="pb-2 font-medium">Reçete Değeri</th>
                    <th className="pb-2 font-medium">Benchmark</th>
                    <th className="pb-2 font-medium">Fark</th>
                    <th className="pb-2 font-medium">Kaynak</th>
                  </tr>
                </thead>
                <tbody>
                  {(result.benchmark_karsilastirmasi.items ?? []).map((item) => (
                    <tr key={item.metric_name} className="border-t border-ink/10">
                      <td className="py-2">{item.metric_label}</td>
                      <td className="py-2 font-mono">
                        {item.recete_degeri ?? "—"} {item.benchmark_unit}
                      </td>
                      <td className="py-2 font-mono">
                        {item.benchmark_value} {item.benchmark_unit}
                      </td>
                      <td className="py-2">
                        {item.fark_pct != null ? (
                          <Badge
                            tone={
                              (HIGHER_IS_BETTER_METRICS.has(item.metric_name) ? item.fark_pct >= 0 : item.fark_pct <= 0)
                                ? "pcr"
                                : "warn"
                            }
                          >
                            {item.fark_pct > 0 ? "+" : ""}
                            {item.fark_pct}%
                          </Badge>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-2 text-xs text-ink/50">{item.benchmark_source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          <Card className="mb-8">
            <CardTitle subtitle="Ambalajın 9 boyutta çok yönlü sürdürülebilirlik durumu — tek bir sayı yerine tam görünüm.">
              Sürdürülebilirlik Karnesi
            </CardTitle>
            <SustainabilityScorecard dimensions={result.surdurulebilirlik_karnesi.dimensions} detailed />
          </Card>

          <Card className="mb-8">
            <CardTitle subtitle="Gerçek reçete verisinden türetilen, somut iyileştirme fırsatları — yeterli veri yoksa öneri hiç gösterilmez.">
              Tasarım İyileştirme Önerileri
            </CardTitle>
            <EcoDesignSuggestions suggestions={ecoDesignSuggestions} />
          </Card>

          {(result.aciklama_maddeleri.length > 0 || result.notable_eliminated.length > 0) && (
            <Card className="mb-8">
              <CardTitle subtitle="Optimizasyon motorunun kararının somut, sayısal gerekçesi.">
                Neden Bu Reçeteyi Seçtin?
              </CardTitle>
              <FinalistExplanation bullets={result.aciklama_maddeleri} eliminated={result.notable_eliminated} />
            </Card>
          )}

          {recipeId && (
            <Card className="mb-8">
              <CardTitle subtitle="Başlangıçtan sonuca, mevcut verilerden derlenen önce-sonra özeti.">
                Dönüşüm Hikâyesi
              </CardTitle>
              <ConversionStoryCard recipeId={recipeId} />
            </Card>
          )}

          {recipeId && (
            <Card className="mb-8">
              <CardTitle subtitle="Teknik şartnameden üretime serbest bırakmaya, mevcut olay kayıtlarından türetilen birleşik görünüm.">
                Yaşam Döngüsü
              </CardTitle>
              <LifecycleTimeline recipeId={recipeId} />
            </Card>
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

          <Card className="mt-6">
            <CardTitle subtitle="Reçete, katman, makine, proses, test, enerji/karbon/fire ve mevzuatın TEK bir birleşik görünümü — reçete yeni bir versiyon aldığında otomatik güncellenir.">
              Ambalajın Dijital İkizi
            </CardTitle>
            {recipeId && (
              <Link
                href={`/dijital-ikiz/${recipeId}`}
                target="_blank"
                className="inline-block text-sm font-medium text-petrol underline underline-offset-2"
              >
                Dijital İkizi Görüntüle
              </Link>
            )}
          </Card>

          <Card className="mt-6">
            <CardTitle subtitle="PCR/kalınlık/fire/yenilenebilir enerji oranını değiştirerek maliyet, karbon, teknik risk ve mevzuat etkisini anında görün — sonuçlar Simülasyon/Tahminidir, kaydedilmez.">
              &quot;Bu Ambalajı Nasıl Daha İyi Yaparım?&quot;
            </CardTitle>
            {recipeId && (
              <Link
                href={`/senaryo-laboratuvari/${recipeId}`}
                target="_blank"
                className="inline-block text-sm font-medium text-petrol underline underline-offset-2"
              >
                Senaryo Laboratuvarını Aç
              </Link>
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
