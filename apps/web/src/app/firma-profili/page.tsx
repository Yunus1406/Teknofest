"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api-client";
import type { CompanyOut, FacilityOut, FacilityUpsert } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { NumberField, TagListField, TextField, TriStateField } from "@/components/ui/FormField";

const EMPTY_FACILITY: FacilityUpsert = {
  name: "",
  address: null,
  code: null,
  production_area_m2: null,
  annual_capacity_tons: null,
  working_days_per_year: null,
  shift_count: null,
  working_hours_per_day: null,
  main_processes: [],
  electricity_consumption_kwh_year: null,
  gas_consumption_m3_year: null,
  renewable_energy_used: null,
  renewable_energy_pct: null,
};

function FacilityForm({
  initial,
  onSubmit,
  submitLabel,
  submitting,
}: {
  initial: FacilityUpsert;
  onSubmit: (v: FacilityUpsert) => void;
  submitLabel: string;
  submitting: boolean;
}) {
  const [form, setForm] = useState<FacilityUpsert>(initial);

  function set<K extends keyof FacilityUpsert>(key: K, value: FacilityUpsert[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <TextField label="Tesis Adı" value={form.name} onChange={(v) => set("name", v)} />
        <TextField label="Tesis Kodu" value={form.code ?? ""} onChange={(v) => set("code", v || null)} />
        <TextField label="Adres" value={form.address ?? ""} onChange={(v) => set("address", v || null)} />
        <NumberField
          label="Üretim Alanı"
          unit="m²"
          value={form.production_area_m2 ?? null}
          onChange={(v) => set("production_area_m2", v)}
        />
        <NumberField
          label="Yıllık Kapasite"
          unit="ton"
          value={form.annual_capacity_tons ?? null}
          onChange={(v) => set("annual_capacity_tons", v)}
        />
        <NumberField
          label="Çalışma Günü/Yıl"
          value={form.working_days_per_year ?? null}
          onChange={(v) => set("working_days_per_year", v)}
        />
        <NumberField label="Vardiya Sayısı" value={form.shift_count ?? null} onChange={(v) => set("shift_count", v)} />
        <NumberField
          label="Çalışma Saati/Gün"
          value={form.working_hours_per_day ?? null}
          onChange={(v) => set("working_hours_per_day", v)}
        />
        <NumberField
          label="Elektrik Tüketimi"
          unit="kWh/yıl"
          value={form.electricity_consumption_kwh_year ?? null}
          onChange={(v) => set("electricity_consumption_kwh_year", v)}
        />
        <NumberField
          label="Doğal Gaz Tüketimi"
          unit="m³/yıl"
          value={form.gas_consumption_m3_year ?? null}
          onChange={(v) => set("gas_consumption_m3_year", v)}
        />
        <TriStateField
          label="Yenilenebilir Enerji Kullanımı"
          value={form.renewable_energy_used ?? null}
          onChange={(v) => set("renewable_energy_used", v)}
        />
        <NumberField
          label="Yenilenebilir Enerji Oranı"
          unit="%"
          value={form.renewable_energy_pct ?? null}
          onChange={(v) => set("renewable_energy_pct", v)}
        />
      </div>
      <TagListField
        label="Ana Üretim Prosesleri"
        value={form.main_processes ?? []}
        onChange={(v) => set("main_processes", v)}
        placeholder="ör. Blown Film Ekstrüzyon, Termoform"
      />
      <Button onClick={() => onSubmit(form)} disabled={submitting || !form.name}>
        {submitting ? "Kaydediliyor…" : submitLabel}
      </Button>
    </div>
  );
}

export default function FirmaProfiliPage() {
  const [company, setCompany] = useState<CompanyOut | null>(null);
  const [facilities, setFacilities] = useState<FacilityOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savingCompany, setSavingCompany] = useState(false);
  const [addingFacility, setAddingFacility] = useState(false);
  const [savingFacilityId, setSavingFacilityId] = useState<string | null>(null);
  const [editingFacilityId, setEditingFacilityId] = useState<string | null>(null);

  const [newCompanyName, setNewCompanyName] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api
      .getCompanyProfile()
      .then((p) => {
        setCompany(p.company);
        setFacilities(p.facilities);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
        else setError(String(e));
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleCreateCompany() {
    if (!newCompanyName) return;
    setCreating(true);
    setError(null);
    try {
      const p = await api.createCompanyProfile({ name: newCompanyName });
      setCompany(p.company);
      setFacilities(p.facilities);
      setNotFound(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setCreating(false);
    }
  }

  function setCompanyField<K extends keyof CompanyOut>(key: K, value: CompanyOut[K]) {
    setCompany((c) => (c ? { ...c, [key]: value } : c));
  }

  async function handleSaveCompany() {
    if (!company) return;
    setSavingCompany(true);
    setError(null);
    try {
      const p = await api.updateCompanyProfile(company);
      setCompany(p.company);
      setFacilities(p.facilities);
    } catch (e) {
      setError(String(e));
    } finally {
      setSavingCompany(false);
    }
  }

  async function handleAddFacility(form: FacilityUpsert) {
    setAddingFacility(true);
    setError(null);
    try {
      const f = await api.createFacility(form);
      setFacilities((fs) => [...fs, f]);
    } catch (e) {
      setError(String(e));
    } finally {
      setAddingFacility(false);
    }
  }

  async function handleUpdateFacility(id: string, form: FacilityUpsert) {
    setSavingFacilityId(id);
    setError(null);
    try {
      const f = await api.updateFacility(id, form);
      setFacilities((fs) => fs.map((x) => (x.id === id ? f : x)));
      setEditingFacilityId(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setSavingFacilityId(null);
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
      <h1 className="mt-1 font-heading text-2xl font-semibold text-ink">Firma Profili ve Üretim Altyapısı</h1>
      <p className="mt-2 text-sm text-ink/60">
        Burada bir kez tanımlanan bilgiler firma hafızasında kalır ve her yeni optimizasyonda otomatik kullanılır.
      </p>
      <Link href="/asama-1-anasayfa" className="mt-2 inline-block text-sm text-petrol underline underline-offset-2">
        ← Ana Ekrana Dön
      </Link>

      {error && (
        <Card className="mt-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      {notFound && !company && (
        <Card className="mt-6">
          <CardTitle subtitle="Sistemde henüz bir firma tanımlı değil. Önce firma unvanını girerek profili oluşturun.">
            Firma Profili Oluştur
          </CardTitle>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <TextField label="Firma Unvanı" value={newCompanyName} onChange={setNewCompanyName} />
            </div>
            <Button onClick={handleCreateCompany} disabled={creating || !newCompanyName}>
              {creating ? "Oluşturuluyor…" : "Oluştur"}
            </Button>
          </div>
        </Card>
      )}

      {company && (
        <>
          <Card className="mt-6">
            <CardTitle>Firma Genel Bilgileri</CardTitle>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
              <TextField label="Unvan" value={company.name} onChange={(v) => setCompanyField("name", v)} />
              <TextField
                label="Ticari Marka"
                value={company.trade_name ?? ""}
                onChange={(v) => setCompanyField("trade_name", v || null)}
              />
              <TextField
                label="Vergi Ülkesi"
                value={company.tax_country ?? ""}
                onChange={(v) => setCompanyField("tax_country", v || null)}
              />
              <TextField label="Ülke" value={company.country ?? ""} onChange={(v) => setCompanyField("country", v || null)} />
              <TextField label="Şehir" value={company.city ?? ""} onChange={(v) => setCompanyField("city", v || null)} />
              <TextField
                label="Web Sitesi"
                value={company.website ?? ""}
                onChange={(v) => setCompanyField("website", v || null)}
              />
              <TextField
                label="Faaliyet Alanı"
                value={company.business_area ?? ""}
                onChange={(v) => setCompanyField("business_area", v || null)}
              />
              <TextField
                label="NACE Kodu"
                value={company.nace_code ?? ""}
                onChange={(v) => setCompanyField("nace_code", v || null)}
              />
              <NumberField
                label="Çalışan Sayısı"
                value={company.employee_count}
                onChange={(v) => setCompanyField("employee_count", v)}
              />
              <NumberField
                label="Yıllık Üretim Kapasitesi"
                unit="ton"
                value={company.annual_production_capacity_tons}
                onChange={(v) => setCompanyField("annual_production_capacity_tons", v)}
              />
              <NumberField
                label="Yıllık Fiili Üretim"
                unit="ton"
                value={company.annual_actual_production_tons}
                onChange={(v) => setCompanyField("annual_actual_production_tons", v)}
              />
              <TriStateField
                label="AB'ye İhracat"
                value={company.exports_to_eu}
                onChange={(v) => setCompanyField("exports_to_eu", v)}
              />
              <TriStateField
                label="Gıda Ambalajı Üretimi"
                value={company.produces_food_packaging}
                onChange={(v) => setCompanyField("produces_food_packaging", v)}
              />
              <TextField
                label="Logo URL"
                value={company.logo_url ?? ""}
                onChange={(v) => setCompanyField("logo_url", v || null)}
              />
            </div>
            <div className="mt-3">
              <TagListField
                label="Ana İhracat Pazarları"
                value={company.main_export_markets}
                onChange={(v) => setCompanyField("main_export_markets", v)}
                placeholder="ör. Almanya, Fransa, İtalya"
              />
            </div>
            <Button className="mt-4" onClick={handleSaveCompany} disabled={savingCompany}>
              {savingCompany ? "Kaydediliyor…" : "Firma Bilgilerini Kaydet"}
            </Button>
          </Card>

          <CardTitle>
            <span className="mt-8 block">Tesisler</span>
          </CardTitle>
          {facilities.map((f) => (
            <Card key={f.id} className="mb-4">
              {editingFacilityId === f.id ? (
                <FacilityForm
                  initial={f}
                  submitLabel="Tesisi Güncelle"
                  submitting={savingFacilityId === f.id}
                  onSubmit={(form) => handleUpdateFacility(f.id, form)}
                />
              ) : (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-heading text-base font-medium text-ink">{f.name}</span>
                      {f.code && <Badge tone="neutral">{f.code}</Badge>}
                    </div>
                    <p className="mt-1 text-sm text-ink/60">{f.address ?? "Adres girilmedi"}</p>
                    {f.annual_capacity_tons != null && (
                      <p className="mt-1 text-xs text-ink/40">Yıllık kapasite: {f.annual_capacity_tons} ton</p>
                    )}
                  </div>
                  <Button variant="secondary" onClick={() => setEditingFacilityId(f.id)}>
                    Düzenle
                  </Button>
                </div>
              )}
            </Card>
          ))}

          <Card>
            <CardTitle>Yeni Tesis Ekle</CardTitle>
            <FacilityForm
              initial={EMPTY_FACILITY}
              submitLabel="Tesisi Ekle"
              submitting={addingFacility}
              onSubmit={handleAddFacility}
            />
          </Card>
        </>
      )}
    </div>
  );
}
