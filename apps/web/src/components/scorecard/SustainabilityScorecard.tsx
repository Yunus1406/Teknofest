import type { SustainabilityScorecardSummaryItemOut, SustainabilityScorecardDimensionOut } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import {
  dataConfidenceFromSourceKind,
  dataConfidenceLabel,
  dataConfidenceTone,
  regulatoryVerdictLabel,
  regulatoryVerdictTone,
  scorecardStatusLabel,
} from "@/lib/labels";

const REGULATORY_VERDICTS = new Set([
  "uygun_gorunuyor",
  "inceleme_gerekli",
  "uygun_degil",
  "veri_eksik",
  "henuz_metodoloji_yok",
]);

function StatusBadge({ durum_metni }: { durum_metni: string | null }) {
  if (!durum_metni) return null;
  if (REGULATORY_VERDICTS.has(durum_metni)) {
    return <Badge tone={regulatoryVerdictTone(durum_metni)}>{regulatoryVerdictLabel(durum_metni)}</Badge>;
  }
  return <Badge tone="neutral">{scorecardStatusLabel(durum_metni)}</Badge>;
}

/** Faz O.2 (Madde 19) — Sürdürülebilirlik Karnesi'nin 9 satırlık görünümü.
 * `detailed=false` (DPP Kamu görünümü): sadece etiket + değer/durum.
 * `detailed=true` (Aşama 12, DPP Yetkili Alan): + referansa göre
 * karşılaştırma yüzdesi + Veri Güveni rozeti (Faz I.4/N.1'in MEVCUT
 * `dataConfidenceFromSourceKind` sistemi reuse edilir, yeni bir eşleme
 * mantığı KURULMAZ). */
export function SustainabilityScorecard({
  dimensions,
  detailed,
}: {
  dimensions: (SustainabilityScorecardSummaryItemOut | SustainabilityScorecardDimensionOut)[];
  detailed: boolean;
}) {
  return (
    <div className="space-y-2">
      {dimensions.map((d) => {
        const full = detailed && "veri_guveni_kind" in d ? (d as SustainabilityScorecardDimensionOut) : null;
        const confidenceLevel = full?.veri_guveni_kind ? dataConfidenceFromSourceKind(full.veri_guveni_kind) : null;

        return (
          <div
            key={d.key}
            className="flex flex-wrap items-center justify-between gap-2 border-b border-ink/10 py-2 text-sm last:border-b-0"
          >
            <span className="font-medium text-ink/70">{d.label}</span>
            <div className="flex flex-wrap items-center gap-2">
              {d.deger != null && (
                <span className="font-mono text-ink/80">
                  {d.deger}
                  {d.birim ? ` ${d.birim}` : ""}
                </span>
              )}
              <StatusBadge durum_metni={d.durum_metni} />
              {full && d.deger != null && (
                full.has_reference && full.karsilastirma_pct != null ? (
                  <Badge tone={full.karsilastirma_pct >= 0 ? "pcr" : "warn"}>
                    {full.karsilastirma_pct > 0 ? "+" : ""}
                    {full.karsilastirma_pct}% (referansa göre)
                  </Badge>
                ) : (
                  <span className="text-xs text-ink/40">Karşılaştırma temeli yok — mutlak durum</span>
                )
              )}
              {full && confidenceLevel && (
                <Badge tone={dataConfidenceTone(confidenceLevel)}>{dataConfidenceLabel(confidenceLevel)}</Badge>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
