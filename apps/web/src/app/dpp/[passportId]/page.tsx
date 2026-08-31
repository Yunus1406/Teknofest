"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api-client";
import type { DigitalProductPassportOut } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { StatTile } from "@/components/ui/StatTile";
import { LayeredCompositionBar } from "@/components/visualizations/LayeredCompositionBar";
import { aggregateToSegments } from "@/lib/composition-segments";
import { carbonEfStatusLabel, carbonEfStatusTone, materialTypeLabel, materialTypeTone } from "@/lib/labels";

/** Dijital Ürün Pasaportu'nun genel web sayfası (QR hedefi). `(flow)`
 * rota grubunun DIŞINDA, case-store'a bağımlı değil — sadece URL'deki
 * pasaport numarasından bağımsız çalışır. Faz C.2'nin API'sinden gelen
 * `public` içeriği varsayılan görünüm; "Genişletilmiş görünüm (Yetkili)"
 * SADECE kullanıcı doğru anahtarı girip yeniden sorgulattığında (ayrı bir
 * istekle) gelir — ticari sır verisi tarayıcıya hiç inmez (bkz.
 * app/services/passport_service.py modül docstring'i). */
export default function DigitalProductPassportPage() {
  const params = useParams<{ passportId: string }>();
  const passportNo = params.passportId;

  const [passport, setPassport] = useState<DigitalProductPassportOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const [showAuthorizedForm, setShowAuthorizedForm] = useState(false);
  const [authorizedKeyInput, setAuthorizedKeyInput] = useState("");
  const [checkingAuthorized, setCheckingAuthorized] = useState(false);
  const [authorizedError, setAuthorizedError] = useState<string | null>(null);

  useEffect(() => {
    if (!passportNo) return;
    setLoading(true);
    setError(null);
    setNotFound(false);
    api
      .getPassport(passportNo)
      .then(setPassport)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
        else setError(String(e));
      })
      .finally(() => setLoading(false));
  }, [passportNo]);

  async function handleViewAuthorized() {
    if (!passportNo || !authorizedKeyInput) return;
    setCheckingAuthorized(true);
    setAuthorizedError(null);
    try {
      const p = await api.getPassport(passportNo, authorizedKeyInput);
      if (!p.authorized) {
        setAuthorizedError("Anahtar hatalı veya Yetkili Alan bu ortamda henüz açık değil.");
      } else {
        setPassport(p);
      }
    } catch (e) {
      setAuthorizedError(String(e));
    } finally {
      setCheckingAuthorized(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <p className="text-sm text-ink/60">Pasaport yükleniyor…</p>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <Card className="border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">
            &quot;{passportNo}&quot; numaralı bir Dijital Ürün Pasaportu bulunamadı.
          </p>
        </Card>
      </div>
    );
  }

  if (error || !passport) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <Card className="border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error ?? "Pasaport yüklenemedi."}</p>
        </Card>
      </div>
    );
  }

  const { header, status_summary, material_summary, environmental, physical_tests, regulatory, version_history } =
    passport.public;
  const segments = aggregateToSegments(
    material_summary.virgin_pct,
    material_summary.pcr_pct,
    material_summary.regranule_pct
  );
  const p1000 = environmental.per_1000_units;

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <p className="font-heading text-sm uppercase tracking-wide text-ink/50">Reçete OS — Dijital Ürün Pasaportu</p>
      <h1 className="mt-1 font-heading text-2xl font-semibold text-ink">
        {header.product_name ?? header.packaging_type ?? "Ambalaj Ürünü"}
      </h1>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-ink/60">
        <Badge tone="petrol">{header.passport_no}</Badge>
        <Badge tone="neutral">Rev.{header.revision}</Badge>
        {header.sku_code && <span>SKU: {header.sku_code}</span>}
      </div>

      {/* Durum özeti */}
      <div className="mt-6 flex flex-wrap gap-2">
        <Badge tone="pcr">Dijital Ürün Kimliği: {status_summary.digital_identity}</Badge>
        <Badge tone="pcr">Reçete: {status_summary.recipe_status}</Badge>
        <Badge tone={status_summary.physical_performance === "Başarısız" ? "warn" : "pcr"}>
          Fiziksel Performans: {status_summary.physical_performance}
        </Badge>
        <Badge tone={status_summary.data_traceability === "Tam" ? "pcr" : "virgin"}>
          Veri İzlenebilirliği: {status_summary.data_traceability}
        </Badge>
        <Badge tone="pcr">PPWR: {status_summary.ppwr_status}</Badge>
      </div>
      <p className="mt-2 text-xs text-ink/40">
        Son Güncelleme: {new Date(status_summary.last_updated).toLocaleString("tr-TR")}
      </p>

      {/* Kimlik bilgisi */}
      <Card className="mt-6">
        <CardTitle>Ürün Kimliği</CardTitle>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-ink/50">Doğrulanmış Reçete</dt>
          <dd>V{header.recipe_version}</dd>
          <dt className="text-ink/50">Üretici / Tesis</dt>
          <dd>{header.company_name ?? "—"} {header.facility_name ? `· ${header.facility_name}` : ""}</dd>
          <dt className="text-ink/50">Üretim Hattı</dt>
          <dd>{header.line_name ?? "—"}</dd>
          <dt className="text-ink/50">Üretim Tarihi</dt>
          <dd>{header.production_date ? new Date(header.production_date).toLocaleDateString("tr-TR") : "—"}</dd>
          <dt className="text-ink/50">Ambalaj Türü</dt>
          <dd>{header.packaging_type ?? "—"}</dd>
          <dt className="text-ink/50">Hedef Pazar</dt>
          <dd>{header.target_market ?? "—"}</dd>
        </dl>
      </Card>

      {/* 1. Malzeme Kimliği */}
      <Card className="mt-6">
        <CardTitle>Malzeme Kimliği</CardTitle>
        <div className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatTile label="Toplam Kalınlık" value={material_summary.total_micron ?? "—"} unit="µm" />
          <StatTile label="Gramaj" value={material_summary.total_gsm ?? "—"} unit="g/m²" />
          <StatTile label="Katman Sayısı" value={material_summary.layer_count} />
          <StatTile label="Katman Yapısı" value={material_summary.layer_structure ?? "—"} />
        </div>
        <LayeredCompositionBar segments={segments} />
        {material_summary.polymers.length > 0 && (
          <p className="mt-3 text-sm text-ink/60">Polimer Ailesi: {material_summary.polymers.join(", ")}</p>
        )}
      </Card>

      {/* 2. Çevresel Performans */}
      <Card className="mt-6">
        <CardTitle subtitle="1.000 satılabilir ambalaj başına">Çevresel Performans</CardTitle>
        {p1000 ? (
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <StatTile label="Virgin" value={(p1000.virgin_kg as number) ?? "—"} unit="kg" />
              <StatTile label="PCR" value={(p1000.pcr_kg as number) ?? "—"} unit="kg" />
              <StatTile label="PIR-Regranül" value={(p1000.regranul_kg as number) ?? "—"} unit="kg" />
              <StatTile label="Karbon" value={(p1000.karbon_kg_co2 as number) ?? "—"} unit="kg CO₂" />
              <StatTile label="Fire" value={(p1000.fire_kg as number) ?? "—"} unit="kg" />
              <StatTile label="Enerji" value={(p1000.enerji_kwh as number) ?? "—"} unit="kWh" />
            </div>
            {p1000.karbon_veri_kalitesi != null && (
              <div className="mt-3">
                <Badge tone={carbonEfStatusTone(p1000.karbon_veri_kalitesi as string)}>
                  {carbonEfStatusLabel(p1000.karbon_veri_kalitesi as string)}
                </Badge>
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-ink/50">Sürdürülebilirlik verisi henüz hesaplanmadı.</p>
        )}
        <p className="mt-4 text-sm text-ink/60">
          {environmental.has_reference && environmental.gains_pct
            ? `Doğrulanmış referansa göre karbon azaltımı: %${environmental.gains_pct.karbon_azaltimi_pct?.toFixed(1) ?? "—"} · maliyet azaltımı: %${environmental.gains_pct.maliyet_azaltimi_pct?.toFixed(1) ?? "—"}`
            : "Karşılaştırma temeli (doğrulanmış bir referans reçete) bulunmuyor — yukarıdaki rakamlar gerçekleşen mutlak performansı gösterir, bir azaltım iddiası taşımaz."}
        </p>
      </Card>

      {/* 3. Teknik ve Kalite Performansı */}
      <Card className="mt-6">
        <CardTitle>Teknik ve Kalite Performansı</CardTitle>
        {physical_tests.length === 0 ? (
          <p className="text-sm text-ink/50">Henüz kayıtlı bir fiziksel test yok.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-ink/50">
                  <th className="pb-2 pr-4 font-medium">Test</th>
                  <th className="pb-2 pr-4 font-medium">Sonuç</th>
                  <th className="pb-2 pr-4 font-medium">Hedef Aralık</th>
                  <th className="pb-2 pr-4 font-medium">Yöntem</th>
                  <th className="pb-2 font-medium">Durum</th>
                </tr>
              </thead>
              <tbody>
                {physical_tests.map((t, i) => (
                  <tr key={i} className="border-t border-ink/10">
                    <td className="py-2 pr-4">{t.test_type}</td>
                    <td className="py-2 pr-4 text-tabular">
                      {t.value} {t.unit}
                    </td>
                    <td className="py-2 pr-4 text-tabular text-ink/60">
                      {t.target_min != null && t.target_max != null ? `${t.target_min}–${t.target_max} ${t.unit}` : "—"}
                    </td>
                    <td className="py-2 pr-4 text-ink/60">{t.test_method ?? "—"}</td>
                    <td className="py-2">
                      <Badge tone={t.passed ? "pcr" : "warn"}>{t.passed ? "Geçti" : "Kaldı"}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* 4. Mevzuat ve Döngüsellik Bilgileri */}
      <Card className="mt-6">
        <CardTitle>Mevzuat ve Döngüsellik Bilgileri</CardTitle>
        <ul className="space-y-2">
          {regulatory.map((r, i) => (
            <li key={i} className="flex items-center gap-2 text-sm">
              <span className="font-mono text-xs text-ink/40">{r.article ?? r.regulation_code}</span>
              <Badge tone={r.verdict === "uygun_gorunuyor" ? "pcr" : r.verdict === "uygun_degil" ? "warn" : "virgin"}>
                {r.verdict === "uygun_gorunuyor" ? "Uygun Görünüyor" : r.verdict === "uygun_degil" ? "Uygun Değil" : "İnceleme Gerekli"}
              </Badge>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-ink/50">{passport.public.regulatory_disclaimer}</p>
      </Card>

      {/* Reçete İzlenebilirliği (versiyon özeti) */}
      <Card className="mt-6">
        <CardTitle>Reçete İzlenebilirliği</CardTitle>
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

      {/* Yetkili Alan */}
      <div className="mt-6">
        {!passport.authorized ? (
          <>
            <button
              className="text-sm font-medium text-petrol underline underline-offset-2"
              onClick={() => setShowAuthorizedForm((s) => !s)}
            >
              {showAuthorizedForm ? "Yetkili Alan girişini gizle" : "Genişletilmiş görünüm (Yetkili) göster"}
            </button>
            {showAuthorizedForm && (
              <Card className="mt-3">
                <p className="mb-3 text-sm text-ink/60">
                  Bu bölüm ticari hammadde grade/lot/tedarikçi detaylarını ve tam üretim izlenebilirlik zincirini
                  içerir — sadece yetkili anahtara sahip kullanıcılar görebilir.
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="password"
                    value={authorizedKeyInput}
                    onChange={(e) => setAuthorizedKeyInput(e.target.value)}
                    placeholder="Yetkili erişim anahtarı"
                    className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm"
                  />
                  <Button onClick={handleViewAuthorized} disabled={checkingAuthorized || !authorizedKeyInput}>
                    {checkingAuthorized ? "Doğrulanıyor…" : "Görüntüle"}
                  </Button>
                </div>
                {authorizedError && <p className="mt-2 text-sm text-warn">{authorizedError}</p>}
              </Card>
            )}
          </>
        ) : (
          <Card className="border-petrol/30 bg-petrol/5">
            <CardTitle subtitle="Sadece yetkili erişimle görünür.">Yetkili Alan — Katman Bazlı Ticari Detay</CardTitle>
            <div className="space-y-2">
              {passport.authorized.layer_materials.map((m, i) => (
                <div key={i} className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-mono text-xs text-ink/40">Katman {m.layer_label}</span>
                  <Badge tone={materialTypeTone(m.material_type ?? "")}>
                    {materialTypeLabel(m.material_type ?? "")} %{m.ratio_pct}
                  </Badge>
                  <span className="text-ink/70">{m.material_name}</span>
                  {m.manufacturer && <span className="text-ink/50">· Üretici: {m.manufacturer}</span>}
                  {m.supplier && <span className="text-ink/50">· Tedarikçi: {m.supplier}</span>}
                  {m.lot_number && <span className="text-ink/50">· Lot: {m.lot_number}</span>}
                </div>
              ))}
            </div>

            <div className="mt-5 border-t border-ink/10 pt-4">
              <CardTitle>Tam İzlenebilirlik Zinciri</CardTitle>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <dt className="text-ink/50">Firma / Tesis</dt>
                <dd>
                  {passport.authorized.traceability.company?.name ?? "—"} ·{" "}
                  {passport.authorized.traceability.facility?.name ?? "—"}
                </dd>
                <dt className="text-ink/50">Makine</dt>
                <dd>{passport.authorized.traceability.machine?.name ?? "—"}</dd>
                <dt className="text-ink/50">Üretim Emirleri</dt>
                <dd>
                  {passport.authorized.traceability.production_orders.length === 0
                    ? "—"
                    : passport.authorized.traceability.production_orders
                        .map((o) => `${o.id.slice(0, 8)}… (${o.operator ?? "operatör kaydı yok"})`)
                        .join(", ")}
                </dd>
              </dl>
            </div>

            {passport.authorized.regulatory_reasoning.length > 0 && (
              <div className="mt-5 border-t border-ink/10 pt-4">
                <CardTitle>Mevzuat Değerlendirme Gerekçeleri</CardTitle>
                <ul className="space-y-2 text-sm text-ink/70">
                  {passport.authorized.regulatory_reasoning.map((r, i) => (
                    <li key={i}>
                      <span className="font-mono text-xs text-ink/40">{r.regulation_code}: </span>
                      {r.reasoning}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
