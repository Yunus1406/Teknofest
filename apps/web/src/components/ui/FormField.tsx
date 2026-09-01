"use client";

import { useState } from "react";
import type { KeyboardEvent } from "react";
import { addTag } from "@/lib/tag-input";

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

// Faz K.5 (Madde 7) — eskiden `value.join(", ")` ile TEK bir string'e
// dönüştürülüp her tuş vuruşunda split/trim/filter edilerek geri
// yazılıyordu; bu, henüz yazılmakta olan ayracı (virgül+boşluk) her
// keystroke'ta silip "AlmanyaFransa" gibi birleşmelere yol açıyordu. Artık
// yazılmakta olan metin kendi AYRI, kontrolsüz taslak state'inde tutulur;
// parent'ın `value: string[]`'i sadece bir etiket TAMAMLANDIĞINDA (Enter/
// virgül/blur) güncellenir -- imleç asla parent'ın re-render'ıyla zıplamaz.
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
  const [draft, setDraft] = useState("");

  function commitDraft() {
    onChange(addTag(value, draft));
    setDraft("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commitDraft();
    } else if (e.key === "Backspace" && draft === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  function removeTag(tag: string) {
    onChange(value.filter((t) => t !== tag));
  }

  return (
    <label className="block">
      <span className="text-xs font-medium text-ink/60">{label}</span>
      <div className="mt-1 flex flex-wrap items-center gap-1.5 rounded-lg border border-ink/15 bg-white/70 px-2 py-1.5">
        {value.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded-full bg-petrol/10 px-2 py-0.5 text-xs text-petrol"
          >
            {tag}
            <button
              type="button"
              className="text-petrol/60 hover:text-petrol"
              onClick={() => removeTag(tag)}
              aria-label={`${tag} etiketini kaldır`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          type="text"
          className="min-w-[8ch] flex-1 border-none bg-transparent text-sm outline-none"
          value={draft}
          placeholder={value.length === 0 ? placeholder : undefined}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={commitDraft}
        />
      </div>
    </label>
  );
}
