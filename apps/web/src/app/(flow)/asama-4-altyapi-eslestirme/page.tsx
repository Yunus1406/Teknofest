"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { LineMatchOut } from "@/lib/types";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { useCaseStore } from "@/stores/case-store";

export default function Stage4Page() {
  const packagingRequestId = useCaseStore((s) => s.packagingRequestId);
  const lineId = useCaseStore((s) => s.lineId);
  const setLineId = useCaseStore((s) => s.setLineId);

  const [matches, setMatches] = useState<LineMatchOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!packagingRequestId) return;
    api
      .getInfrastructureMatches(packagingRequestId)
      .then((m) => {
        setMatches(m);
        if (m.length > 0 && !lineId) setLineId(m[0].line.id);
      })
      .catch((e) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [packagingRequestId]);

  return (
    <div>
      <StageHeader
        no={4}
        title="Firma Altyapısı ve Otomatik Eşleştirme"
        description="Kayıtlı üretim hatları, katman yapıları, kullanılabilir virgin/PCR/regranül hammaddeler ve üretilebilir mikron aralığından uygun olanlar otomatik eşleştirilir."
      />

      {error && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      {matches && matches.length === 0 && (
        <Card className="border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">
            Bu ambalaj türü için uygun bir üretim hattı bulunamadı. Bilgi tabanına hat eklenmeli.
          </p>
        </Card>
      )}

      <div className="space-y-3">
        {matches?.map((m) => (
          <Card
            key={m.line.id}
            className={`cursor-pointer transition-colors ${
              lineId === m.line.id ? "border-petrol/50 ring-1 ring-petrol/30" : ""
            }`}
          >
            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="radio"
                className="mt-1"
                checked={lineId === m.line.id}
                onChange={() => setLineId(m.line.id)}
              />
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <CardTitle>{m.line.name}</CardTitle>
                  <Badge tone="petrol">{m.line.layer_structure}</Badge>
                </div>
                <p className="text-sm text-ink/60">{m.match_reason}</p>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-ink/50">
                  <span>Mikron: {m.line.min_micron}-{m.line.max_micron}</span>
                  <span>Hız: {m.line.line_speed_m_min} m/dk</span>
                  <span>{m.compatible_material_ids.length} uyumlu hammadde</span>
                </div>
              </div>
            </label>
          </Card>
        ))}
      </div>

      <StageNav currentNo={4} nextEnabled={!!lineId} />
    </div>
  );
}
