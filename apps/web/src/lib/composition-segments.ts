import type { LayerCompositionOut, RecipeLayerOut } from "./types";

export type MaterialType = "virgin" | "pcr" | "regranul";

export interface CompositionSegment {
  key: string;
  label: string;
  widthPct: number; // 0-100
  materialType: MaterialType;
  detail?: string; // ör. malzeme adı, tooltip için
}

/** Aşama 1/8/12 gibi yalnızca toplam yüzdelerin bilindiği yerler için 3
 * bantlı (virgin/PCR/regranül) sabit sıralı özet şerit. */
export function aggregateToSegments(virginPct: number, pcrPct: number, regranulePct: number): CompositionSegment[] {
  const segments: CompositionSegment[] = [
    { key: "virgin", label: "Virgin", widthPct: virginPct, materialType: "virgin" },
    { key: "pcr", label: "PCR", widthPct: pcrPct, materialType: "pcr" },
    { key: "regranul", label: "PIR-Regranül", widthPct: regranulePct, materialType: "regranul" },
  ];
  return segments.filter((s) => s.widthPct > 0.01);
}

/** Aşama 5/6/7 gibi tam reçete katman verisinin bilindiği yerler için:
 * her katmanın genişliği kalınlığıyla, katman içi karışım (blend) ise o
 * katmanın payı kendi malzemeleri arasında bölünür — gerçek bir ekstrüzyon
 * film kesitini andırır. `materialTypeOf` katman satırındaki material_id'yi
 * virgin/pcr/regranul türüne çevirir (KB'den gelen malzeme listesiyle). */
export function recipeLayersToSegments(
  layers: RecipeLayerOut[],
  materialTypeOf: (materialId: string) => MaterialType,
  materialNameOf?: (materialId: string) => string
): CompositionSegment[] {
  const totalThickness = layers.reduce((sum, l, idx, arr) => {
    // aynı layer_index birden fazla satırda tekrar etmesin
    const firstOfIndex = arr.findIndex((x) => x.layer_index === l.layer_index) === idx;
    return firstOfIndex ? sum + l.thickness_micron : sum;
  }, 0) || 1;

  const byIndex = new Map<number, RecipeLayerOut[]>();
  for (const l of layers) {
    const list = byIndex.get(l.layer_index) ?? [];
    list.push(l);
    byIndex.set(l.layer_index, list);
  }

  const segments: CompositionSegment[] = [];
  for (const [layerIndex, rows] of [...byIndex.entries()].sort((a, b) => a[0] - b[0])) {
    const layerWidthPct = (rows[0].thickness_micron / totalThickness) * 100;
    for (const row of rows) {
      const widthPct = layerWidthPct * (row.ratio_pct / 100);
      if (widthPct <= 0.01) continue;
      segments.push({
        key: `${layerIndex}-${row.material_id}`,
        label: rows[0].layer_label,
        widthPct,
        materialType: materialTypeOf(row.material_id),
        detail: materialNameOf ? materialNameOf(row.material_id) : undefined,
      });
    }
  }
  return segments;
}

export interface LayerTableRow {
  materialId: string;
  materialType: MaterialType;
  name: string;
  ratioPct: number; // katman İÇİNDEKİ oran (0-100)
}

export interface LayerTableGroup {
  layerIndex: number;
  layerLabel: string;
  thicknessMicron: number;
  rows: LayerTableRow[];
}

/** Faz B.3 — 'PCR hangi katmanda?' sorusuna doğrudan yanıt veren metin
 * tablosu için katman bazlı gruplama (bkz. LayeredCompositionBar'ın görsel
 * şeridiyle aynı veriden türetilir, ama tablo olarak). */
export function recipeLayersToTable(
  layers: RecipeLayerOut[],
  materialTypeOf: (materialId: string) => MaterialType,
  materialNameOf: (materialId: string) => string
): LayerTableGroup[] {
  const byIndex = new Map<number, RecipeLayerOut[]>();
  for (const l of layers) {
    const list = byIndex.get(l.layer_index) ?? [];
    list.push(l);
    byIndex.set(l.layer_index, list);
  }
  return [...byIndex.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([layerIndex, rows]) => ({
      layerIndex,
      layerLabel: rows[0].layer_label,
      thicknessMicron: rows[0].thickness_micron,
      rows: rows.map((r) => ({
        materialId: r.material_id,
        materialType: materialTypeOf(r.material_id),
        name: materialNameOf(r.material_id),
        ratioPct: r.ratio_pct,
      })),
    }));
}

/** Aşama 8 (Dashboard 8) — backend zaten katman kırılımını hazır döner
 * (bkz. schemas/dashboard.py LayerCompositionOut), burada sadece
 * LayerBreakdownTable'ın beklediği şekle çevrilir. */
export function layerCompositionOutToTable(layers: LayerCompositionOut[]): LayerTableGroup[] {
  return layers.map((l) => ({
    layerIndex: l.layer_index,
    layerLabel: l.layer_label,
    thicknessMicron: l.thickness_micron,
    rows: l.materials.map((m) => ({
      materialId: m.material_id,
      materialType: m.material_type,
      name: m.material_name,
      ratioPct: m.ratio_pct,
    })),
  }));
}
