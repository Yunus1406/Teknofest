"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import type {
  AdditiveCreate,
  AdditiveOut,
  MaterialCreate,
  MaterialOut,
  MaterialUpdate,
  PolymerOut,
} from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { NumberField, SelectField, TextField, TriStateField } from "@/components/ui/FormField";
import { SupplierEvidenceBadge } from "@/components/risk/SupplierEvidenceBadge";

type MaterialTab = "virgin" | "pcr" | "regranul";
type Tab = MaterialTab | "additive";

const TAB_LABEL: Record<Tab, string> = {
  virgin: "Virgin",
  pcr: "PCR",
  regranul: "PIR / Regranül",
  additive: "Katkı / Masterbatch",
};

function emptyMaterial(polymerId: string, materialType: MaterialTab): MaterialCreate {
  return {
    polymer_id: polymerId,
    name: "",
    material_type: materialType,
    manufacturer: null,
    supplier: null,
    color: null,
    certification_status: null,
    suitable_layer_position: null,
    mfi_g_10min: null,
    density_g_cm3: null,
    food_contact_eligible: true,
    max_recommended_ratio_pct: 100,
    cost_per_kg: 0,
    currency: "TRY",
    origin_country: null,
    technical_datasheet_ref: null,
    compliance_documents_ref: null,
    stock_qty_kg: null,
    lot_number: null,
    contamination_level: null,
    odor_level: null,
    technical_constraints: null,
    post_consumer_content_pct: null,
    source_process: null,
  };
}

const EMPTY_ADDITIVE: AdditiveCreate = {
  name: "",
  additive_type: "",
  manufacturer: null,
  carrier_polymer: null,
  regulatory_document_ref: null,
  dosage_min_pct: 0,
  dosage_max_pct: 2,
  food_contact_eligible: true,
  cost_per_kg: 0,
};

function MaterialForm({
  materialType,
  polymers,
  initial,
  onSubmit,
  submitLabel,
  submitting,
}: {
  materialType: MaterialTab;
  polymers: PolymerOut[];
  initial: MaterialCreate | MaterialUpdate;
  onSubmit: (v: MaterialCreate) => void;
  submitLabel: string;
  submitting: boolean;
}) {
  const [form, setForm] = useState<MaterialCreate>({
    ...emptyMaterial(polymers[0]?.id ?? "", materialType),
    ...initial,
    material_type: materialType,
  });

  function set<K extends keyof MaterialCreate>(key: K, value: MaterialCreate[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  const polymerCodeToId = new Map(polymers.map((p) => [p.code, p.id]));
  const polymerIdToCode = new Map(polymers.map((p) => [p.id, p.code]));

  return (
    <div className="space-y-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">Genel</p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <TextField label="Ticari Ürün Adı" value={form.name} onChange={(v) => set("name", v)} />
        <SelectField
          label="Polimer Ailesi"
          value={polymerIdToCode.get(form.polymer_id) ?? ""}
          onChange={(v) => set("polymer_id", polymerCodeToId.get(v) ?? "")}
          options={polymers.map((p) => p.code)}
          allowEmpty={false}
        />
        <TextField label="Üretici" value={form.manufacturer ?? ""} onChange={(v) => set("manufacturer", v || null)} />
        <TextField label="Tedarikçi" value={form.supplier ?? ""} onChange={(v) => set("supplier", v || null)} />
        <TextField label="Menşe" value={form.origin_country ?? ""} onChange={(v) => set("origin_country", v || null)} />
        <TextField label="Renk" value={form.color ?? ""} onChange={(v) => set("color", v || null)} />
      </div>

      <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">Teknik Özellikler</p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <NumberField label="MFI/MFR" unit="g/10dk" value={form.mfi_g_10min ?? null} onChange={(v) => set("mfi_g_10min", v)} />
        <NumberField label="Yoğunluk" unit="g/cm³" value={form.density_g_cm3 ?? null} onChange={(v) => set("density_g_cm3", v)} />
        <NumberField
          label="Çekme Dayanımı"
          unit="MPa"
          value={form.tensile_strength_mpa ?? null}
          onChange={(v) => set("tensile_strength_mpa", v)}
        />
        <NumberField label="Uzama" unit="%" value={form.elongation_pct ?? null} onChange={(v) => set("elongation_pct", v)} />
        <TriStateField
          label="Gıda Temas Uygunluğu"
          value={form.food_contact_eligible ?? null}
          onChange={(v) => set("food_contact_eligible", v ?? true)}
        />
        <NumberField
          label="Teknik Kullanım Üst Oranı"
          unit="%"
          value={form.max_recommended_ratio_pct ?? null}
          onChange={(v) => set("max_recommended_ratio_pct", v ?? 100)}
        />
      </div>

      <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">Ticari ve Belge Bilgileri</p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <NumberField label="Birim Fiyat" unit={form.currency ?? "TRY"} value={form.cost_per_kg ?? null} onChange={(v) => set("cost_per_kg", v ?? 0)} />
        <TextField label="Para Birimi" value={form.currency ?? "TRY"} onChange={(v) => set("currency", v || "TRY")} />
        <TextField
          label="Sertifika Durumu"
          value={form.certification_status ?? ""}
          onChange={(v) => set("certification_status", v || null)}
        />
        <TextField
          label="Teknik Veri Föyü Referansı"
          value={form.technical_datasheet_ref ?? ""}
          onChange={(v) => set("technical_datasheet_ref", v || null)}
        />
        <TextField
          label="Uygunluk Belgeleri Referansı"
          value={form.compliance_documents_ref ?? ""}
          onChange={(v) => set("compliance_documents_ref", v || null)}
        />
        <TextField label="Lot Numarası" value={form.lot_number ?? ""} onChange={(v) => set("lot_number", v || null)} />
      </div>

      {materialType === "pcr" && (
        <>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">PCR&apos;a Özgü</p>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <NumberField
              label="Post-Consumer Oranı"
              unit="%"
              value={form.post_consumer_content_pct ?? null}
              onChange={(v) => set("post_consumer_content_pct", v)}
            />
            <TextField
              label="Kontaminasyon Seviyesi"
              value={form.contamination_level ?? ""}
              onChange={(v) => set("contamination_level", v || null)}
            />
            <TextField label="Koku Seviyesi" value={form.odor_level ?? ""} onChange={(v) => set("odor_level", v || null)} />
            <TextField
              label="Teknik Kısıtlar"
              value={form.technical_constraints ?? ""}
              onChange={(v) => set("technical_constraints", v || null)}
            />
          </div>
        </>
      )}

      {materialType === "regranul" && (
        <>
          <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">PIR/Regranül&apos;e Özgü</p>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <TextField
              label="Kaynak Proses"
              value={form.source_process ?? ""}
              onChange={(v) => set("source_process", v || null)}
              placeholder="ör. Ekstrüzyon Kenar Fire Geri Kazanımı"
            />
          </div>
        </>
      )}

      <Button onClick={() => onSubmit(form)} disabled={submitting || !form.name || !form.polymer_id}>
        {submitting ? "Kaydediliyor…" : submitLabel}
      </Button>
    </div>
  );
}

function AdditiveForm({
  initial,
  onSubmit,
  submitLabel,
  submitting,
}: {
  initial: AdditiveCreate;
  onSubmit: (v: AdditiveCreate) => void;
  submitLabel: string;
  submitting: boolean;
}) {
  const [form, setForm] = useState<AdditiveCreate>(initial);

  function set<K extends keyof AdditiveCreate>(key: K, value: AdditiveCreate[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <TextField label="Ad" value={form.name} onChange={(v) => set("name", v)} />
        <TextField label="Katkı Tipi" value={form.additive_type} onChange={(v) => set("additive_type", v)} placeholder="ör. stabilizator" />
        <TextField label="Üretici" value={form.manufacturer ?? ""} onChange={(v) => set("manufacturer", v || null)} />
        <TextField
          label="Taşıyıcı Polimer"
          value={form.carrier_polymer ?? ""}
          onChange={(v) => set("carrier_polymer", v || null)}
          placeholder="ör. PE"
        />
        <TextField
          label="Mevzuat Belgesi Referansı"
          value={form.regulatory_document_ref ?? ""}
          onChange={(v) => set("regulatory_document_ref", v || null)}
        />
        <NumberField label="Min Dozaj" unit="%" value={form.dosage_min_pct ?? null} onChange={(v) => set("dosage_min_pct", v ?? 0)} />
        <NumberField label="Maks Dozaj" unit="%" value={form.dosage_max_pct ?? null} onChange={(v) => set("dosage_max_pct", v ?? 2)} />
        <NumberField label="Birim Fiyat" unit="TRY" value={form.cost_per_kg ?? null} onChange={(v) => set("cost_per_kg", v ?? 0)} />
        <TriStateField
          label="Gıda Temas Uygunluğu"
          value={form.food_contact_eligible ?? null}
          onChange={(v) => set("food_contact_eligible", v ?? true)}
        />
      </div>
      <Button onClick={() => onSubmit(form)} disabled={submitting || !form.name || !form.additive_type}>
        {submitting ? "Kaydediliyor…" : submitLabel}
      </Button>
    </div>
  );
}

export default function HammaddeKutuphanesiPage() {
  const [polymers, setPolymers] = useState<PolymerOut[]>([]);
  const [materials, setMaterials] = useState<MaterialOut[]>([]);
  const [additives, setAdditives] = useState<AdditiveOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("virgin");
  const [adding, setAdding] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.listPolymers(), api.listMaterials(), api.listAdditives()])
      .then(([p, m, a]) => {
        setPolymers(p);
        setMaterials(m);
        setAdditives(a);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  async function handleAddMaterial(form: MaterialCreate) {
    setAdding(true);
    setError(null);
    try {
      const material = await api.createMaterial(form);
      setMaterials((ms) => [...ms, material]);
    } catch (e) {
      setError(String(e));
    } finally {
      setAdding(false);
    }
  }

  async function handleUpdateMaterial(id: string, form: MaterialCreate) {
    setSavingId(id);
    setError(null);
    try {
      const material = await api.updateMaterial(id, form);
      setMaterials((ms) => ms.map((m) => (m.id === id ? material : m)));
      setEditingId(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setSavingId(null);
    }
  }

  async function handleAddAdditive(form: AdditiveCreate) {
    setAdding(true);
    setError(null);
    try {
      const additive = await api.createAdditive(form);
      setAdditives((as) => [...as, additive]);
    } catch (e) {
      setError(String(e));
    } finally {
      setAdding(false);
    }
  }

  async function handleUpdateAdditive(id: string, form: AdditiveCreate) {
    setSavingId(id);
    setError(null);
    try {
      const additive = await api.updateAdditive(id, form);
      setAdditives((as) => as.map((a) => (a.id === id ? additive : a)));
      setEditingId(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setSavingId(null);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <p className="text-sm text-ink/60">Yükleniyor…</p>
      </div>
    );
  }

  const polymerCodeToId = new Map(polymers.map((p) => [p.code, p.id]));
  const polymerIdToCode = new Map(polymers.map((p) => [p.id, p.code]));
  const materialsInTab = tab === "additive" ? [] : materials.filter((m) => m.material_type === tab);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <p className="font-heading text-sm uppercase tracking-wide text-ink/50">Reçete OS</p>
      <h1 className="mt-1 font-heading text-2xl font-semibold text-ink">Hammadde ve Malzeme Kütüphanesi</h1>
      <p className="mt-2 text-sm text-ink/60">
        Firmanın gerçek hammadde/katkı kütüphanesi — optimizasyon motoru bu kayıtlardan besleniyor. Virgin, PCR ve
        PIR/Regranül kasıtlı olarak ayrı formlarda tutulur (bu iki sınıf kod düzeyinde de birbirinden ayrıdır).
      </p>
      <Link href="/asama-1-anasayfa" className="mt-2 inline-block text-sm text-petrol underline underline-offset-2">
        ← Ana Ekrana Dön
      </Link>

      {error && (
        <Card className="mt-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      {polymers.length === 0 && (
        <Card className="mt-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">
            Henüz kayıtlı bir polimer türü yok — yeni hammadde eklemeden önce Bilgi Tabanı&apos;nda en az bir polimer
            tanımlı olmalı.
          </p>
        </Card>
      )}

      <div className="mt-8 flex gap-2 border-b border-ink/10">
        {(["virgin", "pcr", "regranul", "additive"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              setEditingId(null);
            }}
            className={`px-3 py-2 text-sm font-medium ${
              tab === t ? "border-b-2 border-petrol text-petrol" : "text-ink/50 hover:text-ink"
            }`}
          >
            {TAB_LABEL[t]}
          </button>
        ))}
      </div>

      {tab !== "additive" ? (
        <>
          <CardTitle>
            <span className="mt-6 block">
              Kayıtlı {TAB_LABEL[tab]} Hammaddeler ({materialsInTab.length})
            </span>
          </CardTitle>
          {materialsInTab.map((material) => (
            <Card key={material.id} className="mb-4">
              {editingId === material.id ? (
                <MaterialForm
                  materialType={tab}
                  polymers={polymers}
                  initial={material}
                  submitLabel="Hammaddeyi Güncelle"
                  submitting={savingId === material.id}
                  onSubmit={(form) => handleUpdateMaterial(material.id, form)}
                />
              ) : (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-heading text-base font-medium text-ink">{material.name}</span>
                      <Badge tone="petrol">{polymerIdToCode.get(material.polymer_id) ?? "?"}</Badge>
                      {material.food_contact_eligible && <Badge tone="neutral">Gıda Temaslı</Badge>}
                    </div>
                    <p className="mt-1 text-sm text-ink/60">
                      {material.manufacturer ?? "Veri Girilmedi"} · {material.cost_per_kg} {material.currency}/kg
                      {material.material_type === "pcr" && material.post_consumer_content_pct != null
                        ? ` · %${material.post_consumer_content_pct} post-consumer`
                        : ""}
                    </p>
                    <div className="mt-2">
                      <SupplierEvidenceBadge materialId={material.id} />
                    </div>
                  </div>
                  <Button variant="secondary" onClick={() => setEditingId(material.id)}>
                    Düzenle
                  </Button>
                </div>
              )}
            </Card>
          ))}

          <Card>
            <CardTitle>Yeni {TAB_LABEL[tab]} Hammadde Ekle</CardTitle>
            {polymers.length > 0 && (
              <MaterialForm
                materialType={tab}
                polymers={polymers}
                initial={emptyMaterial(polymers[0].id, tab)}
                submitLabel="Hammaddeyi Ekle"
                submitting={adding}
                onSubmit={handleAddMaterial}
              />
            )}
          </Card>
        </>
      ) : (
        <>
          <CardTitle>
            <span className="mt-6 block">Kayıtlı Katkılar / Masterbatch ({additives.length})</span>
          </CardTitle>
          {additives.map((additive) => (
            <Card key={additive.id} className="mb-4">
              {editingId === additive.id ? (
                <AdditiveForm
                  initial={additive}
                  submitLabel="Katkıyı Güncelle"
                  submitting={savingId === additive.id}
                  onSubmit={(form) => handleUpdateAdditive(additive.id, form)}
                />
              ) : (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-heading text-base font-medium text-ink">{additive.name}</span>
                      <Badge tone="neutral">{additive.additive_type}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-ink/60">
                      {additive.manufacturer ?? "Veri Girilmedi"} · %{additive.dosage_min_pct}-{additive.dosage_max_pct} dozaj
                    </p>
                  </div>
                  <Button variant="secondary" onClick={() => setEditingId(additive.id)}>
                    Düzenle
                  </Button>
                </div>
              )}
            </Card>
          ))}

          <Card>
            <CardTitle>Yeni Katkı / Masterbatch Ekle</CardTitle>
            <AdditiveForm initial={EMPTY_ADDITIVE} submitLabel="Katkıyı Ekle" submitting={adding} onSubmit={handleAddAdditive} />
          </Card>
        </>
      )}
    </div>
  );
}
