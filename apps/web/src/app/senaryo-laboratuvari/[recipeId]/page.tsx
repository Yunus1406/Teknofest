"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api-client";
import type { ScenarioOverridesIn, ScenarioResultOut } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { NumberField } from "@/components/ui/FormField";
import { dataConfidenceFromSourceKind, dataConfidenceLabel, dataConfidenceTone } from "@/lib/labels";

const ROWS: { key: keyof ScenarioResultOut["baseline"]; label: string; unit: string }[] = [
  { key: "virgin_pct", label: "Virgin", unit: "%" },
  { key: "pcr_pct", label: "PCR", unit: "%" },
  { key: "regranul_pct", label: "PIR-Regranül", unit: "%" },
  { key: "total_micron", label: "Toplam Kalınlık", unit: "µm" },
  { key: "maliyet_tl_per_kg", label: "Maliyet", unit: "TL/kg" },
  { key: "karbon_kg_co2_per_kg", label: "Karbon (Malzeme)", unit: "kg CO₂/kg" },
  { key: "fire_pct", label: "Fire", unit: "%" },
  { key: "yenilenebilir_enerji_pct", label: "Yenilenebilir Enerji", unit: "%" },
  { key: "enerji_karbon_yogunlugu_kg_co2_per_kwh", label: "Enerji Karbon Yoğunluğu", unit: "kg CO₂/kWh" },
];

function formatCell(v: number | string | null | undefined): string {
  if (typeof v !== "number") return "—";
  return v.toFixed(2);
}

/** Faz P.1 (Madde 20) — "Bu Ambalajı Nasıl Daha İyi Yaparım?" Senaryo
 * Laboratuvarı. DPP/Dijital İkiz sayfaları gibi standalone (case-store'a
 * bağımlı değil, reçete kimliği route param'dan gelir). Hiçbir sonuç DB'ye
 * yazılmaz -- gerçek üretim verisiyle KARIŞTIRILMAMASI için her sayı
 * "Simülasyon/Tahmini" olarak etiketlenir. */
export default function ScenarioLabPage() {
  const params = useParams<{ recipeId: string }>();
  const recipeId = params.recipeId;

  const [form, setForm] = useState<{
    pcr_pct: number | null;
    kalinlik_micron: number | null;
    fire_pct: number | null;
    yenilenebilir_enerji_pct: number | null;
  }>({ pcr_pct: null, kalinlik_micron: null, fire_pct: null, yenilenebilir_enerji_pct: null });

  const [result, setResult] = useState<ScenarioResultOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof typeof form>(key: K, value: number | null) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleRun() {
    setLoading(true);
    setError(null);
    try {
      const overrides: ScenarioOverridesIn = {
        pcr_pct: form.pcr_pct,
        kalinlik_micron: form.kalinlik_micron,
        fire_pct: form.fire_pct,
        yenilenebilir_enerji_pct: form.yenilenebilir_enerji_pct,
      };
      const r = await api.runScenario(recipeId, overrides);
      setResult(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  const anyOverrideSet = Object.values(form).some((v) => v != null);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <p className="font-heading text-sm uppercase tracking-wide text-ink/50">Reçete OS — Senaryo Laboratuvarı</p>
      <h1 className="mt-1 font-heading text-2xl font-semibold text-ink">
        &quot;Bu Ambalajı Nasıl Daha İyi Yaparım?&quot;
      </h1>
      <p className="mt-2 text-sm text-ink/60">
        Doğrulanmış reçete üzerinde what-if senaryoları çalıştırın; sonuçlar gerçek hesaplama motoruyla üretilir
        ama hiçbir şey kaydedilmez.
      </p>

      <Card className="mt-6 border-virgin/30 bg-virgin/5">
        <p className="text-sm text-virgin">
          Bu ekrandaki tüm sonuçlar <strong>Simülasyon/Tahmini</strong>&apos;dir — gerçek üretim verisiyle
          KARIŞTIRILMAMALIDIR.
        </p>
      </Card>

      <Card className="mt-6">
        <CardTitle subtitle="Değiştirmek istemediğiniz alanları boş bırakın.">Senaryo Parametreleri</CardTitle>
        <div className="grid grid-cols-2 gap-4">
          <NumberField label="Hedef PCR Oranı" unit="%" value={form.pcr_pct} onChange={(v) => set("pcr_pct", v)} />
          <NumberField
            label="Hedef Toplam Kalınlık"
            unit="µm"
            value={form.kalinlik_micron}
            onChange={(v) => set("kalinlik_micron", v)}
          />
          <NumberField label="Hedef Fire Oranı" unit="%" value={form.fire_pct} onChange={(v) => set("fire_pct", v)} />
          <NumberField
            label="Hedef Yenilenebilir Enerji Oranı"
            unit="%"
            value={form.yenilenebilir_enerji_pct}
            onChange={(v) => set("yenilenebilir_enerji_pct", v)}
          />
        </div>
        <Button className="mt-4" onClick={handleRun} disabled={loading || !anyOverrideSet}>
          {loading ? "Hesaplanıyor…" : "Senaryoyu Hesapla"}
        </Button>
        {error && <p className="mt-2 text-sm text-warn">{error}</p>}
      </Card>

      {result && (
        <>
          <Card className="mt-6">
            <CardTitle>Mevcut · Senaryo · Fark</CardTitle>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-ink/40">
                    <th className="py-1 pr-4 font-normal"></th>
                    <th className="py-1 pr-4 font-normal">Mevcut</th>
                    <th className="py-1 pr-4 font-normal">Senaryo</th>
                    <th className="py-1 pr-4 font-normal">Fark</th>
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map((row) => (
                    <tr key={row.key} className="border-t border-ink/5">
                      <td className="py-1.5 pr-4 text-ink/50">{row.label}</td>
                      <td className="py-1.5 pr-4 font-mono">
                        {formatCell(result.baseline[row.key])} {row.unit}
                      </td>
                      <td className="py-1.5 pr-4 font-mono">
                        {formatCell(result.senaryo[row.key])} {row.unit}
                      </td>
                      <td className="py-1.5 pr-4 font-mono">
                        {(() => {
                          const f = result.fark[row.key as string];
                          if (f == null) return "—";
                          return `${f > 0 ? "+" : ""}${f.toFixed(2)} ${row.unit}`;
                        })()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex items-center gap-2">
              {(() => {
                const level = dataConfidenceFromSourceKind(result.senaryo.veri_kaynagi);
                return level ? <Badge tone={dataConfidenceTone(level)}>{dataConfidenceLabel(level)}</Badge> : null;
              })()}
              <span className="text-xs text-ink/40">Senaryo sütunu için geçerli</span>
            </div>
            {result.uyarilar.length > 0 && (
              <div className="mt-3 space-y-1">
                {result.uyarilar.map((w, i) => (
                  <p key={i} className="text-sm text-warn">
                    ⚠ {w}
                  </p>
                ))}
              </div>
            )}
          </Card>

          <Card className="mt-6">
            <CardTitle>Teknik Risk</CardTitle>
            <div className="flex flex-wrap gap-2">
              {result.teknik_risk.kalinlik_hat_sinirlari_icinde != null && (
                <Badge tone={result.teknik_risk.kalinlik_hat_sinirlari_icinde ? "pcr" : "warn"}>
                  Kalınlık: {result.teknik_risk.kalinlik_hat_sinirlari_icinde ? "Hat Sınırları İçinde" : "Hat Sınırları Dışında"}
                </Badge>
              )}
              {result.teknik_risk.pcr_tavanini_asiyor_mu != null && (
                <Badge tone={result.teknik_risk.pcr_tavanini_asiyor_mu ? "warn" : "pcr"}>
                  PCR: {result.teknik_risk.pcr_tavanini_asiyor_mu ? "Malzeme Tavanını Aşıyor" : "Tavan İçinde"}
                </Badge>
              )}
            </div>
            {result.teknik_risk.notlar.map((n, i) => (
              <p key={i} className="mt-2 text-sm text-ink/60">
                {n}
              </p>
            ))}
          </Card>

          <Card className="mt-6">
            <CardTitle>Mevzuat (PPWR Md.7 — PCR İçeriği)</CardTitle>
            {result.mevzuat.hedef_pct != null ? (
              <div className="flex items-center gap-2">
                <span className="text-sm text-ink/60">2030 hedefi: %{result.mevzuat.hedef_pct}</span>
                <Badge tone={result.mevzuat.hedefi_karsiliyor_mu ? "pcr" : "warn"}>
                  {result.mevzuat.hedefi_karsiliyor_mu ? "Hedefi Karşılıyor" : "Hedefin Altında"}
                </Badge>
              </div>
            ) : (
              <p className="text-sm text-ink/50">{result.mevzuat.not}</p>
            )}
          </Card>
        </>
      )}

      <Link href="/asama-1-anasayfa" className="mt-6 inline-block text-sm text-petrol underline underline-offset-2">
        ← Ana Ekrana Dön
      </Link>
    </div>
  );
}
