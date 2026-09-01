import type { EcoDesignSuggestionOut } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { dataConfidenceFromSourceKind, dataConfidenceLabel, dataConfidenceTone } from "@/lib/labels";

/** Faz P.2 (Madde 21) — Otomatik Eko-Tasarım Önerileri. Her öneri gerçek
 * veriden türetilir (bkz. apps/api/app/services/eco_design_service.py);
 * boş liste normaldir (yeterli veri/eşik yoksa öneri hiç üretilmez). */
export function EcoDesignSuggestions({ suggestions }: { suggestions: EcoDesignSuggestionOut[] }) {
  if (suggestions.length === 0) {
    return <p className="text-sm text-ink/50">Bu reçete için şu an somut bir tasarım iyileştirme önerisi yok.</p>;
  }
  return (
    <ul className="space-y-2">
      {suggestions.map((s) => {
        const level = dataConfidenceFromSourceKind(s.veri_guveni_kind);
        return (
          <li key={s.key} className="rounded-lg bg-ink/[0.03] p-3">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-ink/80">{s.title}</p>
              {level && <Badge tone={dataConfidenceTone(level)}>{dataConfidenceLabel(level)}</Badge>}
            </div>
            <p className="mt-1 text-sm text-ink/60">{s.detay_metni}</p>
          </li>
        );
      })}
    </ul>
  );
}
