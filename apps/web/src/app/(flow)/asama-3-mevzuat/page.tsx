"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { RegulatoryAssessmentSummaryOut, RegulationOut } from "@/lib/types";
import { ActiveCaseSummary } from "@/components/layout/ActiveCaseSummary";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import {
  evidenceStatusLabel,
  evidenceStatusTone,
  recyclabilityDimensionLabel,
  regulatoryVerdictLabel,
  regulatoryVerdictTone,
} from "@/lib/labels";
import { useCaseStore } from "@/stores/case-store";

export default function Stage3Page() {
  const packagingRequestId = useCaseStore((s) => s.packagingRequestId);
  const [result, setResult] = useState<RegulatoryAssessmentSummaryOut | null>(null);
  const [regulations, setRegulations] = useState<RegulationOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Faz L.1 — "Bu kural neden uygulanıyor?" panelinin açık/kapalı durumu.
  const [expandedTrail, setExpandedTrail] = useState<Set<string>>(new Set());

  function toggleTrail(id: string) {
    setExpandedTrail((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

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
      <ActiveCaseSummary />

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
                  {a.decision_trail && (
                    <div className="mt-3 border-t border-ink/10 pt-3">
                      <button
                        type="button"
                        className="text-xs font-medium text-petrol hover:underline"
                        onClick={() => toggleTrail(a.id)}
                      >
                        {expandedTrail.has(a.id) ? "▾" : "▸"} Bu kural neden uygulanıyor?
                      </button>
                      {expandedTrail.has(a.id) && (
                        <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1.5 font-mono text-xs text-ink/60 md:grid-cols-2">
                          <div>
                            <dt className="text-ink/40">1. Hedef Pazar</dt>
                            <dd>
                              {a.decision_trail.hedef_pazar ?? "—"} ({a.decision_trail.hedef_pazar_ab_mi === "evet" ? "AB" : a.decision_trail.hedef_pazar_ab_mi === "hayir" ? "AB dışı" : "belirsiz"})
                            </dd>
                          </div>
                          <div>
                            <dt className="text-ink/40">2. Ambalaj Malzemesi</dt>
                            <dd>{a.decision_trail.ambalaj_malzemesi_tahmini}</dd>
                          </div>
                          <div>
                            <dt className="text-ink/40">3. Kullanım</dt>
                            <dd>{a.decision_trail.kullanim_alani}</dd>
                          </div>
                          <div>
                            <dt className="text-ink/40">4. Gıda Teması</dt>
                            <dd>{a.decision_trail.gida_temasi ? "Evet" : "Hayır"}</dd>
                          </div>
                          <div>
                            <dt className="text-ink/40">5. Ambalaj Kategorisi</dt>
                            <dd>{a.decision_trail.ambalaj_kategorisi}</dd>
                          </div>
                          <div>
                            <dt className="text-ink/40">6. İstisnalar</dt>
                            <dd>{a.decision_trail.istisna ?? "—"}</dd>
                          </div>
                          <div>
                            <dt className="text-ink/40">7. Uygulanacak Madde</dt>
                            <dd>{a.decision_trail.uygulanan_madde}</dd>
                          </div>
                          <div>
                            <dt className="text-ink/40">8. Hedef Tarih</dt>
                            <dd>{a.decision_trail.hedef_tarih ?? "—"}</dd>
                          </div>
                        </dl>
                      )}
                    </div>
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

          {result.evidence_checklist.length > 0 && (
            <Card className="mt-6">
              <CardTitle subtitle="Gıda temaslı ambalajlar için otomatik kanıt yönetim listesi -- her kanıt ayrı ayrı takip edilir.">
                Kanıt Durumu
              </CardTitle>
              <ul className="mt-2 space-y-2">
                {result.evidence_checklist.map((item, i) => (
                  <li key={i} className="flex items-start justify-between gap-4 border-t border-ink/10 pt-2 first:border-t-0 first:pt-0">
                    <div>
                      <p className="text-sm font-medium text-ink">
                        {item.evidence_type}
                        {item.regulation_ref && <span className="ml-1.5 font-mono text-xs text-ink/40">({item.regulation_ref})</span>}
                      </p>
                      <p className="text-xs text-ink/60">{item.notes}</p>
                    </div>
                    <Badge tone={evidenceStatusTone(item.status)}>{evidenceStatusLabel(item.status)}</Badge>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}

      <StageNav currentNo={3} nextEnabled={!!result} />
    </div>
  );
}
