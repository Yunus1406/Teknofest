"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import type { ProductSkuCreate, ProductSkuDetailOut, ProductSkuOut } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { NumberField, TextField, TriStateField } from "@/components/ui/FormField";
import {
  materialTypeLabel,
  materialTypeTone,
  physicalTestResultLabel,
  physicalTestResultTone,
  regulatoryVerdictLabel,
  regulatoryVerdictTone,
} from "@/lib/labels";

const EMPTY_SKU: ProductSkuCreate = {
  sku_code: "",
  product_name: "",
  packaging_type: "",
  usage_area: "",
  customer: null,
  customer_sector: null,
  target_market: "",
  food_contact: false,
  film_thickness_micron: null,
  gsm: null,
  layer_count: null,
  layer_structure: null,
};

function SkuForm({
  initial,
  onSubmit,
  submitLabel,
  submitting,
}: {
  initial: ProductSkuCreate;
  onSubmit: (v: ProductSkuCreate) => void;
  submitLabel: string;
  submitting: boolean;
}) {
  const [form, setForm] = useState<ProductSkuCreate>(initial);

  function set<K extends keyof ProductSkuCreate>(key: K, value: ProductSkuCreate[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <TextField label="SKU Kodu" value={form.sku_code} onChange={(v) => set("sku_code", v)} />
        <TextField label="Ürün Adı" value={form.product_name} onChange={(v) => set("product_name", v)} />
        <TextField label="Ambalaj Türü" value={form.packaging_type} onChange={(v) => set("packaging_type", v)} />
        <TextField label="Kullanım Alanı" value={form.usage_area} onChange={(v) => set("usage_area", v)} />
        <TextField label="Müşteri" value={form.customer ?? ""} onChange={(v) => set("customer", v || null)} />
        <TextField
          label="Müşteri Sektörü"
          value={form.customer_sector ?? ""}
          onChange={(v) => set("customer_sector", v || null)}
          placeholder="ör. gıda, kozmetik"
        />
        <TextField label="Hedef Pazar" value={form.target_market} onChange={(v) => set("target_market", v)} />
        <TriStateField
          label="Gıda Teması"
          value={form.food_contact ?? null}
          onChange={(v) => set("food_contact", v ?? false)}
        />
        <TextField
          label="Katman Yapısı"
          value={form.layer_structure ?? ""}
          onChange={(v) => set("layer_structure", v || null)}
          placeholder="ör. A/B/A"
        />
        <NumberField label="Katman Sayısı" value={form.layer_count ?? null} onChange={(v) => set("layer_count", v)} />
        <NumberField label="Kalınlık" unit="µm" value={form.film_thickness_micron ?? null} onChange={(v) => set("film_thickness_micron", v)} />
        <NumberField label="Gramaj" unit="g/m²" value={form.gsm ?? null} onChange={(v) => set("gsm", v)} />
      </div>
      <Button
        onClick={() => onSubmit(form)}
        disabled={submitting || !form.sku_code || !form.product_name || !form.packaging_type || !form.usage_area || !form.target_market}
      >
        {submitting ? "Kaydediliyor…" : submitLabel}
      </Button>
    </div>
  );
}

function TraceabilityBlock({
  trace,
  onViewPassport,
}: {
  trace: NonNullable<ProductSkuDetailOut["traceability"]>;
  onViewPassport: (recipeId: string) => void;
}) {
  return (
    <div className="mt-4 space-y-4 border-t border-ink/10 pt-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">Reçete</p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm">
          <Badge tone="petrol">V{trace.recipe.version}</Badge>
          <span className="text-ink/60">{trace.recipe.status}</span>
          {trace.recipe.is_verified && <Badge tone="pcr">Doğrulandı</Badge>}
        </div>
      </div>

      {trace.machine && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">Üretildiği Hat</p>
          <p className="mt-1 text-sm text-ink/70">
            {trace.machine.name} {trace.machine.process_type ? `· ${trace.machine.process_type}` : ""}
          </p>
        </div>
      )}

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">Kullanılan Hammaddeler</p>
        <div className="mt-1 space-y-1">
          {trace.layers.map((l, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-mono text-xs text-ink/40">Katman {l.layer_label}</span>
              {l.material && (
                <Badge tone={materialTypeTone(l.material.material_type)}>
                  {materialTypeLabel(l.material.material_type)} %{l.ratio_pct}
                </Badge>
              )}
              <span className="text-ink/70">{l.material?.name ?? "—"}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">Fiziksel Test Sonuçları</p>
        {trace.physical_tests.length === 0 ? (
          <p className="mt-1 text-sm text-ink/50">Henüz kayıtlı bir fiziksel test yok.</p>
        ) : (
          <div className="mt-1 space-y-1">
            {trace.physical_tests.map((t, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-ink/70">{t.test_type}</span>
                <span className="text-tabular text-ink/60">
                  {t.value} {t.unit}
                </span>
                <Badge tone={physicalTestResultTone(t.result)}>{physicalTestResultLabel(t.result)}</Badge>
              </div>
            ))}
          </div>
        )}
      </div>

      {trace.regulatory_assessments.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">Mevzuat</p>
          <div className="mt-1 space-y-1">
            {trace.regulatory_assessments.map((r, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="font-mono text-xs text-ink/40">{r.regulation_code ?? "—"}</span>
                <Badge tone={regulatoryVerdictTone(r.verdict)}>{regulatoryVerdictLabel(r.verdict)}</Badge>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={() => onViewPassport(trace.recipe_id)}
        className="text-sm font-medium text-petrol underline underline-offset-2"
      >
        Dijital Ürün Pasaportu&apos;nu Görüntüle →
      </button>
    </div>
  );
}

export default function UrunPortfoyuPage() {
  const router = useRouter();
  const [skus, setSkus] = useState<ProductSkuOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ProductSkuDetailOut | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    api
      .listProductSkus()
      .then(setSkus)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  async function handleAdd(form: ProductSkuCreate) {
    setAdding(true);
    setError(null);
    try {
      const sku = await api.createProductSku(form);
      setSkus((ss) => [...ss, sku]);
    } catch (e) {
      setError(String(e));
    } finally {
      setAdding(false);
    }
  }

  async function handleUpdate(id: string, form: ProductSkuCreate) {
    setSavingId(id);
    setError(null);
    try {
      const sku = await api.updateProductSku(id, form);
      setSkus((ss) => ss.map((s) => (s.id === id ? sku : s)));
      setEditingId(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setSavingId(null);
    }
  }

  async function handleExpand(id: string) {
    if (expandedId === id) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(id);
    setDetail(null);
    setDetailLoading(true);
    try {
      const d = await api.getProductSkuDetail(id);
      setDetail(d);
    } catch (e) {
      setError(String(e));
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleViewPassport(recipeId: string) {
    setError(null);
    try {
      const passport = await api.createOrGetPassport(recipeId);
      router.push(`/dpp/${passport.public.header.passport_no}`);
    } catch (e) {
      setError(String(e));
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <p className="text-sm text-ink/60">Yükleniyor…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <p className="font-heading text-sm uppercase tracking-wide text-ink/50">Reçete OS</p>
      <h1 className="mt-1 font-heading text-2xl font-semibold text-ink">Ürün Portföyü</h1>
      <p className="mt-2 text-sm text-ink/60">
        Firmanın mevcut ürünleri/SKU&apos;ları — yeni bir ambalaj çalışması, burada kayıtlı gerçek üretim
        hafızasından beslenebilir.
      </p>
      <Link href="/asama-1-anasayfa" className="mt-2 inline-block text-sm text-petrol underline underline-offset-2">
        ← Ana Ekrana Dön
      </Link>

      {error && (
        <Card className="mt-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      <CardTitle>
        <span className="mt-8 block">Kayıtlı Ürünler ({skus.length})</span>
      </CardTitle>
      {skus.map((sku) => (
        <Card key={sku.id} className="mb-4">
          {editingId === sku.id ? (
            <SkuForm
              initial={sku}
              submitLabel="Ürünü Güncelle"
              submitting={savingId === sku.id}
              onSubmit={(form) => handleUpdate(sku.id, form)}
            />
          ) : (
            <>
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-heading text-base font-medium text-ink">{sku.product_name}</span>
                    <Badge tone="petrol">{sku.sku_code}</Badge>
                    {sku.customer_sector && <Badge tone="neutral">{sku.customer_sector}</Badge>}
                    {sku.current_recipe_id && <Badge tone="pcr">Doğrulanmış Reçete Var</Badge>}
                  </div>
                  <p className="mt-1 text-sm text-ink/60">
                    {sku.packaging_type} · {sku.usage_area}
                    {sku.customer ? ` · ${sku.customer}` : ""}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => handleExpand(sku.id)}>
                    {expandedId === sku.id ? "Detayı Gizle" : "Üretim İzlenebilirliği"}
                  </Button>
                  <Link href={`/uygunluk-dosyasi/${sku.id}`}>
                    <Button variant="secondary">Uygunluk Dosyası</Button>
                  </Link>
                  <Button variant="secondary" onClick={() => setEditingId(sku.id)}>
                    Düzenle
                  </Button>
                </div>
              </div>

              {expandedId === sku.id && (
                <>
                  {detailLoading && <p className="mt-4 text-sm text-ink/50">Yükleniyor…</p>}
                  {!detailLoading && detail && detail.traceability && (
                    <TraceabilityBlock trace={detail.traceability} onViewPassport={handleViewPassport} />
                  )}
                  {!detailLoading && detail && !detail.traceability && (
                    <p className="mt-4 border-t border-ink/10 pt-4 text-sm text-ink/50">
                      Bu ürün için henüz doğrulanmış bir üretim/reçete kaydı yok — üretim izlenebilirliği ilk
                      doğrulanmış reçeteden sonra burada görünecek.
                    </p>
                  )}
                </>
              )}
            </>
          )}
        </Card>
      ))}

      <Card>
        <CardTitle>Yeni Ürün Ekle</CardTitle>
        <SkuForm initial={EMPTY_SKU} submitLabel="Ürünü Ekle" submitting={adding} onSubmit={handleAdd} />
      </Card>
    </div>
  );
}
