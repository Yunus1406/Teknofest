"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api-client";
import type { DigitalTwinOut } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { StatTile } from "@/components/ui/StatTile";
import {
  materialTypeLabel,
  materialTypeTone,
  physicalTestResultLabel,
  physicalTestResultTone,
  regulatoryVerdictLabel,
  regulatoryVerdictTone,
} from "@/lib/labels";

/** Faz O.1 (Madde 18) — Ambalajın Dijital İkizi: mevcut izlenebilirlik
 * zincirinin (Reçete+Katman+Makine+Test+Mevzuat) proses/sürdürülebilirlik/
 * versiyon zinciriyle birleşik görünümü. Her mount'ta TAZE fetch edilir —
 * statik bir snapshot değil (bkz. apps/api/app/services/
 * digital_twin_service.py modül docstring'i). Paylaşılan komponent: hem
 * `/dijital-ikiz/[recipeId]` standalone sayfasında hem DPP'nin Yetkili Alan
 * sekmesinde AYNI render mantığı kullanılır. */
export function DigitalTwinView({ recipeId }: { recipeId: string }) {
  const [twin, setTwin] = useState<DigitalTwinOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    api
      .getDigitalTwin(recipeId)
      .then(setTwin)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
        else setError(String(e));
      })
      .finally(() => setLoading(false));
  }, [recipeId]);

  if (loading) return <p className="text-sm text-ink/60">Dijital İkiz yükleniyor…</p>;
  if (notFound) return <p className="text-sm text-warn">Bu reçete için bir Dijital İkiz bulunamadı.</p>;
  if (error || !twin) return <p className="text-sm text-warn">{error ?? "Dijital İkiz yüklenemedi."}</p>;

  const { traceability, process_parameters, sustainability_per_1000_units: p1000, version_history } = twin;

  return (
    <div className="space-y-4">
      {/* Reçete & Katman */}
      <Card>
        <CardTitle>Reçete ve Katman Yapısı</CardTitle>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatTile label="Versiyon" value={`V${traceability.recipe.version}`} />
          <StatTile label="Durum" value={traceability.recipe.status} />
          <StatTile label="Toplam Kalınlık" value={traceability.recipe.total_micron ?? "—"} unit="µm" />
          <StatTile label="Gramaj" value={traceability.recipe.total_gsm ?? "—"} unit="g/m²" />
        </div>
        <div className="mt-3 space-y-1.5">
          {traceability.layers.map((l) => (
            <div key={l.layer_index} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-mono text-xs text-ink/40">Katman {l.layer_label}</span>
              {l.material && (
                <Badge tone={materialTypeTone(l.material.material_type)}>
                  {materialTypeLabel(l.material.material_type)} %{l.ratio_pct}
                </Badge>
              )}
              <span className="text-ink/70">{l.material?.name ?? "—"}</span>
              {l.carbon_ef && (
                <span className="text-xs text-ink/40">
                  {l.carbon_ef.ef_value} {l.carbon_ef.unit}
                  {l.carbon_ef.is_demo_placeholder ? " (varsayımsal EF)" : ""}
                </span>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Makine & Proses */}
      <Card>
        <CardTitle>Makine ve Proses</CardTitle>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-ink/50">Firma / Tesis</dt>
          <dd>
            {traceability.company?.name ?? "—"} · {traceability.facility?.name ?? "—"}
          </dd>
          <dt className="text-ink/50">Üretim Hattı</dt>
          <dd>{traceability.machine?.name ?? "—"}</dd>
          <dt className="text-ink/50">Proses Tipi</dt>
          <dd>{traceability.machine?.process_type ?? "—"}</dd>
        </dl>
        {process_parameters.length > 0 && (
          <div className="mt-3 border-t border-ink/10 pt-3">
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink/40">
              Tipik Proses Parametreleri
            </p>
            <ul className="space-y-1 text-sm text-ink/60">
              {process_parameters.map((p, i) => (
                <li key={i}>
                  {p.parameter_name}: {p.typical_min ?? "—"}–{p.typical_max ?? "—"} {p.unit}
                  {p.is_demo_placeholder && <span className="ml-1 text-xs text-ink/40">(varsayımsal)</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {/* Fiziksel Testler */}
      <Card>
        <CardTitle>Fiziksel Testler</CardTitle>
        {traceability.physical_tests.length === 0 ? (
          <p className="text-sm text-ink/50">Henüz kayıtlı bir fiziksel test yok.</p>
        ) : (
          <div className="space-y-1.5">
            {traceability.physical_tests.map((t, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="text-ink/70">{t.test_type}</span>
                <span className="font-mono text-xs text-ink/50">
                  {t.value} {t.unit}
                </span>
                <Badge tone={physicalTestResultTone(t.result)}>{physicalTestResultLabel(t.result)}</Badge>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Enerji + Karbon + Fire */}
      <Card>
        <CardTitle subtitle="1.000 satılabilir ambalaj başına">Enerji, Karbon ve Fire</CardTitle>
        {p1000 ? (
          <>
            <div className="mb-2">
              <Badge tone={p1000.is_actual ? "pcr" : "virgin"}>
                {p1000.is_actual ? "Gerçekleşen" : "Tahmini"}
              </Badge>
            </div>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatTile label="Karbon" value={(p1000.karbon_kg_co2 as number) ?? "—"} unit="kg CO₂" />
              <StatTile label="Fire" value={(p1000.fire_kg as number) ?? "—"} unit="kg" />
              <StatTile label="Enerji" value={(p1000.enerji_kwh as number) ?? "—"} unit="kWh" />
              <StatTile label="Virgin" value={(p1000.virgin_kg as number) ?? "—"} unit="kg" />
            </div>
          </>
        ) : (
          <p className="text-sm text-ink/50">Sürdürülebilirlik verisi henüz hesaplanmadı.</p>
        )}
      </Card>

      {/* Mevzuat */}
      <Card>
        <CardTitle>Mevzuat</CardTitle>
        {traceability.regulatory_assessments.length === 0 ? (
          <p className="text-sm text-ink/50">Henüz bir mevzuat değerlendirmesi yok.</p>
        ) : (
          <ul className="space-y-2">
            {traceability.regulatory_assessments.map((r, i) => (
              <li key={i} className="flex items-center gap-2 text-sm">
                <span className="font-mono text-xs text-ink/40">{r.regulation_code ?? "—"}</span>
                <Badge tone={regulatoryVerdictTone(r.verdict)}>{regulatoryVerdictLabel(r.verdict)}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Versiyon Zinciri */}
      <Card>
        <CardTitle>Versiyon Zinciri</CardTitle>
        <ol className="space-y-2">
          {version_history.map((v) => (
            <li key={v.id} className="flex items-center gap-3 text-sm">
              <span className="font-mono text-xs text-ink/40">{new Date(v.created_at).toLocaleDateString("tr-TR")}</span>
              <Badge tone="petrol">V{v.version}</Badge>
              <span className="text-ink/60">{v.status}</span>
              {v.is_verified && <Badge tone="pcr">Doğrulandı</Badge>}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
