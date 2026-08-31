import type { LayerTableGroup } from "@/lib/composition-segments";
import { formatPct, materialTypeLabel, materialTypeTone } from "@/lib/labels";
import { Badge } from "@/components/ui/Badge";

/** Faz B.3 — LayeredCompositionBar'ın görsel şeridini tamamlayan metin
 * tablosu: "Katman B (çekirdek): LDPE %70, PCR %30" gibi — hangi malzemenin
 * HANGİ KATMANDA olduğu artık tek bakışta okunabilir (görsel şeritte hover
 * gerektiren bilgi burada doğrudan metin). */
export function LayerBreakdownTable({ groups }: { groups: LayerTableGroup[] }) {
  if (groups.length === 0) return null;
  return (
    <div className="mt-3 space-y-2">
      {groups.map((g) => (
        <div key={g.layerIndex} className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-mono text-xs text-ink/40">
            Katman {g.layerLabel} ({g.thicknessMicron.toFixed(0)} µm)
          </span>
          {g.rows.map((r) => (
            <Badge key={r.materialId} tone={materialTypeTone(r.materialType)}>
              {materialTypeLabel(r.materialType)} {formatPct(r.ratioPct)} · {r.name}
            </Badge>
          ))}
        </div>
      ))}
    </div>
  );
}
