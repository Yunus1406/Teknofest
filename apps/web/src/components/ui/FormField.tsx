"use client";

/** Faz E — Firma Profili/Makine Parkı/Hammadde Kütüphanesi/Ürün Portföyü
 * formlarında paylaşılan girdi alanları. `TriStateField` özellikle önemli:
 * bilinmeyen bir E/H alanı ASLA "Hayır"a düşmez, açıkça "Veri Girilmedi"
 * seçeneği taşır (bkz. apps/api/app/models/company.py modül docstring'i). */

export function TextField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-ink/60">{label}</span>
      <input
        type="text"
        className="mt-1 w-full rounded-lg border border-ink/15 bg-white/70 px-2.5 py-1.5 text-sm"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

export function NumberField({
  label,
  value,
  onChange,
  unit,
}: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  unit?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-ink/60">
        {label}
        {unit ? ` (${unit})` : ""}
      </span>
      <input
        type="number"
        step="any"
        className="mt-1 w-full rounded-lg border border-ink/15 bg-white/70 px-2.5 py-1.5 text-sm font-mono"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
      />
    </label>
  );
}

export function TriStateField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean | null;
  onChange: (v: boolean | null) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-ink/60">{label}</span>
      <select
        className="mt-1 w-full rounded-lg border border-ink/15 bg-white/70 px-2.5 py-1.5 text-sm"
        value={value === null ? "unknown" : value ? "yes" : "no"}
        onChange={(e) => onChange(e.target.value === "unknown" ? null : e.target.value === "yes")}
      >
        <option value="unknown">Veri Girilmedi</option>
        <option value="yes">Evet</option>
        <option value="no">Hayır</option>
      </select>
    </label>
  );
}

export function SelectField({
  label,
  value,
  onChange,
  options,
  allowEmpty = true,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
  allowEmpty?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-ink/60">{label}</span>
      <select
        className="mt-1 w-full rounded-lg border border-ink/15 bg-white/70 px-2.5 py-1.5 text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {allowEmpty && <option value="">— Seçilmedi —</option>}
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}

export function TagListField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-ink/60">{label} (virgülle ayırın)</span>
      <input
        type="text"
        className="mt-1 w-full rounded-lg border border-ink/15 bg-white/70 px-2.5 py-1.5 text-sm"
        value={value.join(", ")}
        placeholder={placeholder}
        onChange={(e) =>
          onChange(
            e.target.value
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          )
        }
      />
    </label>
  );
}
