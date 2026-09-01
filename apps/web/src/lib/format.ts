// Faz H.1 alanları (virgin_kg, pcr_kg, regranul_kg, fire_kg, enerji_kwh)
// API'de `float | None = None` olarak tanımlı; JSON'da hem `null` hem alan
// tamamen YOK (undefined) olarak gelebilir. `!== null` tek başına
// undefined'ı yakalamaz ve ardından gelen `.toFixed()` çağrısı çöker --
// bu yüzden `typeof v === "number"` kullanılır (Aşama 12/DPP'nin
// formatTripleCell'indeki güvenli desenin eşleniği).
export function formatOptionalKg(v: number | null | undefined, unit: string): string | null {
  return typeof v === "number" ? `${v.toFixed(2)} ${unit}` : null;
}
