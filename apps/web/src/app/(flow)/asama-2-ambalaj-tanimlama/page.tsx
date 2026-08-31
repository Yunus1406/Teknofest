"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import type { PackagingRequestCreate, SpecExtractionOut } from "@/lib/types";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useCaseStore } from "@/stores/case-store";

const emptyForm: PackagingRequestCreate = {
  packaging_type: "",
  usage_area: "",
  product: "",
  target_market: "",
  food_contact: false,
  target_volume_units: 0,
  dimensions: { length_mm: null, width_mm: null, height_mm: null },
};

function confidenceTone(c: string | undefined): "pcr" | "virgin" | "warn" | "neutral" {
  if (c === "yuksek") return "pcr";
  if (c === "orta") return "virgin";
  if (c === "dusuk") return "warn";
  return "neutral";
}

export default function Stage2Page() {
  const router = useRouter();
  const setPackagingRequestId = useCaseStore((s) => s.setPackagingRequestId);

  const [form, setForm] = useState<PackagingRequestCreate>(emptyForm);
  const [specText, setSpecText] = useState("");
  const [extraction, setExtraction] = useState<SpecExtractionOut | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draftRequestId, setDraftRequestId] = useState<string | null>(null);

  async function ensureDraftRequest(): Promise<string> {
    if (draftRequestId) return draftRequestId;
    const created = await api.createPackagingRequest(form);
    setDraftRequestId(created.id);
    return created.id;
  }

  async function handleExtract() {
    if (!specText.trim()) return;
    setExtracting(true);
    setError(null);
    try {
      const id = await ensureDraftRequest();
      const result = await api.extractSpecFromText(id, specText);
      setExtraction(result);
      setForm((f) => ({
        ...f,
        packaging_type: result.packaging_type ?? f.packaging_type,
        usage_area: result.usage_area ?? f.usage_area,
        product: result.product ?? f.product,
        target_market: result.target_market ?? f.target_market,
        food_contact: result.food_contact ?? f.food_contact,
        target_volume_units: result.target_volume_units ?? f.target_volume_units,
        dimensions: { ...f.dimensions, ...result.dimensions },
      }));
    } catch (e) {
      setError(String(e));
    } finally {
      setExtracting(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const created = draftRequestId
        ? await api.updatePackagingRequest(draftRequestId, form)
        : await api.createPackagingRequest(form);
      setPackagingRequestId(created.id);
      router.push("/asama-3-mevzuat");
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <StageHeader
        no={2}
        title="Ambalaj Tanımlama"
        description="Ürün bilgilerini girin veya teknik şartname yükleyin — sistem bilgileri otomatik çıkarır, siz sadece eksik/şüpheli alanları kontrol edersiniz."
      />

      <Card className="mb-6">
        <CardTitle subtitle="Serbest metin şartname yapıştırın; sistem alanları otomatik çıkarır (düşük güvenli alanlar aşağıda işaretlenir).">
          Teknik Şartname (opsiyonel)
        </CardTitle>
        <textarea
          className="w-full rounded-lg border border-ink/15 bg-white/70 p-3 text-sm"
          rows={4}
          placeholder="Örn: 230x230mm tek kullanımlık gıda tabağı, AB pazarı, 500.000 adet/yıl..."
          value={specText}
          onChange={(e) => setSpecText(e.target.value)}
        />
        <div className="mt-3 flex items-center gap-3">
          <Button type="button" variant="secondary" onClick={handleExtract} disabled={extracting || !specText.trim()}>
            {extracting ? "Çıkarılıyor…" : "Alanları Çıkar"}
          </Button>
          {extraction && (
            <span className="text-xs text-ink/50">
              Aşağıdaki formda otomatik dolduruldu — lütfen kontrol edin.
            </span>
          )}
        </div>
        {extraction && Object.keys(extraction.field_confidence).length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {Object.entries(extraction.field_confidence).map(([field, conf]) => (
              <Badge key={field} tone={confidenceTone(conf)}>
                {field}: {conf}
              </Badge>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <form className="grid grid-cols-1 gap-4 md:grid-cols-2" onSubmit={handleSubmit}>
          <Field label="Ambalaj Türü" required>
            <input
              className="input"
              required
              value={form.packaging_type}
              onChange={(e) => setForm({ ...form, packaging_type: e.target.value })}
              placeholder="örn. plastik tabak"
            />
          </Field>
          <Field label="Kullanım Alanı" required>
            <input
              className="input"
              required
              value={form.usage_area}
              onChange={(e) => setForm({ ...form, usage_area: e.target.value })}
              placeholder="örn. gıda servisi"
            />
          </Field>
          <Field label="Ürün" required>
            <input
              className="input"
              required
              value={form.product}
              onChange={(e) => setForm({ ...form, product: e.target.value })}
              placeholder="örn. tek kullanımlık yemek tabağı"
            />
          </Field>
          <Field label="Hedef Pazar" required>
            <input
              className="input"
              required
              value={form.target_market}
              onChange={(e) => setForm({ ...form, target_market: e.target.value })}
              placeholder="örn. AB"
            />
          </Field>
          <Field label="Üretim Miktarı (adet)">
            <input
              type="number"
              className="input"
              value={form.target_volume_units}
              onChange={(e) => setForm({ ...form, target_volume_units: Number(e.target.value) })}
            />
          </Field>
          <Field label="Gıda Teması">
            <label className="flex items-center gap-2 text-sm text-ink/70">
              <input
                type="checkbox"
                checked={form.food_contact}
                onChange={(e) => setForm({ ...form, food_contact: e.target.checked })}
              />
              Ambalaj gıda ile doğrudan temas ediyor
            </label>
          </Field>
          <Field label="Uzunluk (mm)">
            <input
              type="number"
              className="input"
              value={form.dimensions.length_mm ?? ""}
              onChange={(e) =>
                setForm({ ...form, dimensions: { ...form.dimensions, length_mm: Number(e.target.value) || null } })
              }
            />
          </Field>
          <Field label="Genişlik (mm)">
            <input
              type="number"
              className="input"
              value={form.dimensions.width_mm ?? ""}
              onChange={(e) =>
                setForm({ ...form, dimensions: { ...form.dimensions, width_mm: Number(e.target.value) || null } })
              }
            />
          </Field>

          {error && <p className="md:col-span-2 text-sm text-warn">{error}</p>}

          <div className="md:col-span-2">
            <Button type="submit" disabled={submitting}>
              {submitting ? "Kaydediliyor…" : "Kaydet ve Mevzuat Değerlendirmesine Geç"}
            </Button>
          </div>
        </form>
      </Card>

      <style jsx global>{`
        .input {
          width: 100%;
          border-radius: 0.5rem;
          border: 1px solid rgba(19, 34, 30, 0.15);
          background: rgba(255, 255, 255, 0.7);
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
        }
      `}</style>

      <StageNav currentNo={2} nextEnabled={false} />
    </div>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink/60">
        {label}
        {required ? " *" : ""}
      </span>
      {children}
    </label>
  );
}
