"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { RegulatoryAssessmentSummaryOut, RegulationOut } from "@/lib/types";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { recyclabilityDimensionLabel, regulatoryVerdictLabel, regulatoryVerdictTone } from "@/lib/labels";
import { useCaseStore } from "@/stores/case-store";

export default function Stage3Page() {
  const packagingRequestId = useCaseStore((s) => s.packagingRequestId);
  const [result, setResult] = useState<RegulatoryAssessmentSummaryOut | null>(null);
  const [regulations, setRegulations] = useState<RegulationOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!packagingRequestId) return;
    Promise.all([api.runRegulatoryAssessment(packagingRequestId), api.listRegulations()])
      .then(([r, regs]) => {
        setResult(r);
        setRegulations(regs);
      })
      .catch((e) => setError(String(e)));
  }, [packagingRequestId]);

  const regById = Object.fromEntries(regulations.map((r) => [r.id, r]));

  return (
    <div>
      <StageHeader
        no={3}
        title="Mevzuat ve Tasarım Kriterleri"
        description="Otomatik değerlendirme — AB PPWR kapsamı, ambalaj minimizasyonu, geri dönüştürülebilirlik, geri dönüştürülmüş içerik ve gıda teması kriterleri kontrol edilir."
      />

      {!packagingRequestId && (
        <Card className="border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">Önce Aşama 2&apos;de bir ambalaj talebi oluşturmalısınız.</p>
        </Card>
      )}
      {error && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      {result && (
        <>
          <Card className="mb-6">
            <div className="flex items-center justify-between">
              <CardTitle>Genel Sonuç</CardTitle>
              <Badge tone={regulatoryVerdictTone(result.overall_verdict)}>
                {regulatoryVerdictLabel(result.overall_verdict)}
              </Badge>
            </div>
          </Card>

          <div className="space-y-3">
            {result.assessments.map((a) => {
              const reg = regById[a.regulation_id];
              return (
                <Card key={a.id}>
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-mono text-xs text-ink/40">{reg?.code}</p>
                      <p className="font-heading text-sm font-medium text-ink">{reg?.title}</p>
                    </div>
                    <Badge tone={regulatoryVerdictTone(a.verdict)}>{regulatoryVerdictLabel(a.verdict)}</Badge>
                  </div>
                  {a.reasoning.includes(" | ") ? (
                    <ul className="mt-2 space-y-1">
                      {a.reasoning.split(" | ").map((part, i) => (
                        <li key={i} className="text-sm text-ink/60">
                          {part}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-ink/60">{a.reasoning}</p>
                  )}
                  {a.recyclability_breakdown && (
                    <div className="mt-3 border-t border-ink/10 pt-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-ink/40">
                        Geri Dönüştürülebilirlik Kırılımı
                      </p>
                      <ul className="mt-1.5 space-y-1.5">
                        {a.recyclability_breakdown.dimensions.map((d, i) => (
                          <li key={i} className="text-sm text-ink/60">
                            <span className="font-medium text-ink/70">{recyclabilityDimensionLabel(d.dimension)}</span>
                            {d.weight_pct != null ? ` (%${d.weight_pct})` : ""}: {d.criterion_text}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        </>
      )}

      <StageNav currentNo={3} nextEnabled={!!result} />
    </div>
  );
}
