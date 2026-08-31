"use client";

import { useState } from "react";
import type { ProductionLineCreate } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { NumberField, SelectField, TagListField, TextField, TriStateField } from "@/components/ui/FormField";

/** Faz E.2'de kurulan makine parkı formu — Faz G.3'te Aşama 4'ün "Yeni
 * Makine Tanımla" akışıyla da paylaşılabilmesi için `/makine-parki`
 * sayfasından buraya taşındı (kod tekrarı yok, tek kaynak). */

export const MACHINE_CLASSES = [
  "Blown Film Extrusion",
  "Cast Film Extrusion",
  "Mono Extrusion",
  "ABA Extrusion",
  "ABC Extrusion",
  "Flexographic Printing",
  "Rotogravure Printing",
  "Solvent-based Lamination",
  "Solvent-free Lamination",
  "Extrusion Lamination",
  "Slitting",
  "Cutting",
  "Bag Making",
  "Thermoforming",
  "Injection Molding",
  "Blow Molding",
  "Recycling/Regranulation",
  "Gravimetric Dosing",
  "Auxiliary Equipment",
];

export const LAYER_STRUCTURE_TYPES = ["Mono", "ABA", "ABC", "ABCBA"];
export const AVAILABILITY_OPTIONS = ["aktif", "bakimda", "devre_disi"];

export const EMPTY_LINE: ProductionLineCreate = {
  name: "",
  process_type: null,
  layer_structure: "",
  layer_count: 1,
  min_micron: 0,
  max_micron: 0,
  manufacturer: null,
  model: null,
  install_year: null,
  layer_structure_type: null,
  screw_diameter_mm: null,
  ld_ratio: null,
  min_line_speed_m_min: null,
  max_line_speed_m_min: null,
  nominal_capacity_kg_year: null,
  actual_capacity_kg_year: null,
  suitable_polymer_codes: [],
  pcr_capable: null,
  pir_capable: null,
  max_pcr_technical_pct: null,
  max_pir_technical_pct: null,
  gravimetric_dosing_equipped: null,
  online_thickness_control: null,
  energy_metering_equipped: null,
  average_waste_rate_pct: null,
  availability_status: null,
};

export function MachineForm({
  initial,
  onSubmit,
  submitLabel,
  submitting,
}: {
  initial: ProductionLineCreate;
  onSubmit: (v: ProductionLineCreate) => void;
  submitLabel: string;
  submitting: boolean;
}) {
  const [form, setForm] = useState<ProductionLineCreate>(initial);

  function set<K extends keyof ProductionLineCreate>(key: K, value: ProductionLineCreate[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  return (
    <div className="space-y-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">Genel</p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <TextField label="Makine Adı" value={form.name} onChange={(v) => set("name", v)} />
        <SelectField
          label="Makine Ana Sınıfı"
          value={form.process_type ?? ""}
          onChange={(v) => set("process_type", v || null)}
          options={MACHINE_CLASSES}
        />
        <TextField label="Üretici" value={form.manufacturer ?? ""} onChange={(v) => set("manufacturer", v || null)} />
        <TextField label="Model" value={form.model ?? ""} onChange={(v) => set("model", v || null)} />
        <NumberField label="Üretim/Kurulum Yılı" value={form.install_year ?? null} onChange={(v) => set("install_year", v)} />
        <SelectField
          label="Kullanılabilirlik Durumu"
          value={form.availability_status ?? ""}
          onChange={(v) => set("availability_status", v || null)}
          options={AVAILABILITY_OPTIONS}
        />
      </div>

      <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">Teknik Yapı</p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <TextField
          label="Katman Yapısı"
          value={form.layer_structure}
          onChange={(v) => set("layer_structure", v)}
          placeholder="ör. A/B/A"
        />
        <SelectField
          label="Katman Yapısı Tipi"
          value={form.layer_structure_type ?? ""}
          onChange={(v) => set("layer_structure_type", v || null)}
          options={LAYER_STRUCTURE_TYPES}
        />
        <NumberField label="Katman Sayısı" value={form.layer_count ?? null} onChange={(v) => set("layer_count", v ?? 1)} />
        <NumberField label="Ekstrüder Sayısı" value={form.extruder_count ?? null} onChange={(v) => set("extruder_count", v)} />
        <NumberField label="Vida Çapı" unit="mm" value={form.screw_diameter_mm ?? null} onChange={(v) => set("screw_diameter_mm", v)} />
        <NumberField label="L/D Oranı" value={form.ld_ratio ?? null} onChange={(v) => set("ld_ratio", v)} />
      </div>

      <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">Kapasite ve Hız</p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <NumberField label="Min Kalınlık" unit="µm" value={form.min_micron} onChange={(v) => set("min_micron", v ?? 0)} />
        <NumberField label="Maks Kalınlık" unit="µm" value={form.max_micron} onChange={(v) => set("max_micron", v ?? 0)} />
        <NumberField label="Min Gramaj" unit="g/m²" value={form.min_gsm ?? null} onChange={(v) => set("min_gsm", v)} />
        <NumberField label="Maks Gramaj" unit="g/m²" value={form.max_gsm ?? null} onChange={(v) => set("max_gsm", v)} />
        <NumberField label="Maks Genişlik" unit="mm" value={form.max_width_mm ?? null} onChange={(v) => set("max_width_mm", v)} />
        <NumberField
          label="Min Hat Hızı"
          unit="m/dk"
          value={form.min_line_speed_m_min ?? null}
          onChange={(v) => set("min_line_speed_m_min", v)}
        />
        <NumberField
          label="Maks Hat Hızı"
          unit="m/dk"
          value={form.max_line_speed_m_min ?? null}
          onChange={(v) => set("max_line_speed_m_min", v)}
        />
        <NumberField
          label="Nominal Kapasite"
          unit="kg/yıl"
          value={form.nominal_capacity_kg_year ?? null}
          onChange={(v) => set("nominal_capacity_kg_year", v)}
        />
        <NumberField
          label="Fiili Kapasite"
          unit="kg/yıl"
          value={form.actual_capacity_kg_year ?? null}
          onChange={(v) => set("actual_capacity_kg_year", v)}
        />
      </div>

      <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">PCR/PIR Kabiliyeti</p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <TriStateField label="PCR Kullanım Kabiliyeti" value={form.pcr_capable ?? null} onChange={(v) => set("pcr_capable", v)} />
        <TriStateField label="PIR Kullanım Kabiliyeti" value={form.pir_capable ?? null} onChange={(v) => set("pir_capable", v)} />
        <NumberField
          label="Maks Teknik PCR Oranı"
          unit="%"
          value={form.max_pcr_technical_pct ?? null}
          onChange={(v) => set("max_pcr_technical_pct", v)}
        />
        <NumberField
          label="Maks Teknik PIR Oranı"
          unit="%"
          value={form.max_pir_technical_pct ?? null}
          onChange={(v) => set("max_pir_technical_pct", v)}
        />
        <NumberField label="Min Dozaj" unit="%" value={form.min_dosage_pct ?? null} onChange={(v) => set("min_dosage_pct", v)} />
        <NumberField label="Maks Dozaj" unit="%" value={form.max_dosage_pct ?? null} onChange={(v) => set("max_dosage_pct", v)} />
      </div>

      <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">Donanım ve Performans</p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        <TriStateField
          label="Gravimetrik Dozajlama"
          value={form.gravimetric_dosing_equipped ?? null}
          onChange={(v) => set("gravimetric_dosing_equipped", v)}
        />
        <TriStateField
          label="Online Kalınlık Kontrolü"
          value={form.online_thickness_control ?? null}
          onChange={(v) => set("online_thickness_control", v)}
        />
        <TriStateField
          label="Enerji Ölçümü"
          value={form.energy_metering_equipped ?? null}
          onChange={(v) => set("energy_metering_equipped", v)}
        />
        <NumberField
          label="Ortalama Enerji Tüketimi"
          unit="kWh/kg"
          value={form.energy_kwh_per_kg ?? null}
          onChange={(v) => set("energy_kwh_per_kg", v ?? 0)}
        />
        <NumberField
          label="Ortalama Fire Oranı"
          unit="%"
          value={form.average_waste_rate_pct ?? null}
          onChange={(v) => set("average_waste_rate_pct", v)}
        />
      </div>

      <TagListField
        label="Uygun Polimerler"
        value={form.suitable_polymer_codes ?? []}
        onChange={(v) => set("suitable_polymer_codes", v)}
        placeholder="ör. PE, PP, PET"
      />
      <TagListField
        label="Desteklenen Ambalaj Türleri"
        value={form.supported_packaging_types ?? []}
        onChange={(v) => set("supported_packaging_types", v)}
        placeholder="ör. esnek film ambalaj"
      />

      <Button onClick={() => onSubmit(form)} disabled={submitting || !form.name || !form.layer_structure}>
        {submitting ? "Kaydediliyor…" : submitLabel}
      </Button>
    </div>
  );
}
