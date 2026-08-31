import type { ProductionLineCreate, ProductionLineOut } from "./types";

/** Faz G.3 — Aşama 4'ün "Kayıtlı Makineden Hat Oluştur" özelliği. Backend'in
 * `app/services/line_composition.py::derive_composite_line_defaults`
 * fonksiyonuyla AYNI mantığı istemci tarafında uygular (sunucuya gidip
 * gelmeden anlık önizleme için) -- ama bu sadece bir ÖNERİ üretir, kullanıcı
 * submit öncesi her alanı düzenleyebilir. Backend tarafı kendi testleriyle
 * (tests/test_line_composition.py) doğrulanır; bu dosyanın tek görevi aynı
 * kesişim/min/AND kurallarını tekrarlamaktır. */
export function deriveCompositeLineDefaults(components: ProductionLineOut[]): Partial<ProductionLineCreate> {
  if (components.length === 0) return {};

  const result: Partial<ProductionLineCreate> = {
    name: components.map((c) => c.name).join(" + "),
    component_line_ids: components.map((c) => c.id),
    min_micron: Math.max(...components.map((c) => c.min_micron)),
    max_micron: Math.min(...components.map((c) => c.max_micron)),
  };

  const speeds = components.map((c) => c.line_speed_m_min).filter((v): v is number => !!v);
  if (speeds.length > 0) result.line_speed_m_min = Math.min(...speeds);

  for (const field of ["nominal_capacity_kg_year", "actual_capacity_kg_year"] as const) {
    const values = components.map((c) => c[field]).filter((v): v is number => v != null);
    if (values.length > 0) result[field] = Math.min(...values);
  }

  for (const field of ["pcr_capable", "pir_capable"] as const) {
    const values = components.map((c) => c[field]).filter((v): v is boolean => v != null);
    if (values.length > 0) result[field] = values.every((v) => v);
  }

  for (const field of ["max_pcr_technical_pct", "max_pir_technical_pct"] as const) {
    const values = components.map((c) => c[field]).filter((v): v is number => v != null);
    if (values.length > 0) result[field] = Math.min(...values);
  }

  const polymerSets = components.map((c) => c.suitable_polymer_codes).filter((codes) => codes.length > 0);
  if (polymerSets.length > 0) {
    const intersection = polymerSets.reduce((acc, codes) => acc.filter((c) => codes.includes(c)));
    result.suitable_polymer_codes = [...intersection].sort();
  }

  const extrusionComponent = components.find((c) => c.process_type?.toLowerCase().includes("extrusion"));
  if (extrusionComponent) {
    result.layer_structure = extrusionComponent.layer_structure;
    result.layer_count = extrusionComponent.layer_count;
  }

  return result;
}
