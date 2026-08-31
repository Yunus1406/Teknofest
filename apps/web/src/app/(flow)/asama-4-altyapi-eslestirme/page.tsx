"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { LineMatchOut, ProductionLineCreate, ProductionLineOut } from "@/lib/types";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EMPTY_LINE, MachineForm } from "@/components/machine-park/MachineForm";
import { deriveCompositeLineDefaults } from "@/lib/line-composition";
import { useCaseStore } from "@/stores/case-store";

type AddMode = "closed" | "choose" | "compose" | "new_machine";

export default function Stage4Page() {
  const packagingRequestId = useCaseStore((s) => s.packagingRequestId);
  const lineId = useCaseStore((s) => s.lineId);
  const setLineId = useCaseStore((s) => s.setLineId);

  const [matches, setMatches] = useState<LineMatchOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [addMode, setAddMode] = useState<AddMode>("closed");
  const [allLines, setAllLines] = useState<ProductionLineOut[]>([]);
  const [selectedComponentIds, setSelectedComponentIds] = useState<Set<string>>(new Set());
  const [composeForm, setComposeForm] = useState<ProductionLineCreate | null>(null);
  const [addingLine, setAddingLine] = useState(false);

  function refreshMatches() {
    if (!packagingRequestId) return;
    api
      .getInfrastructureMatches(packagingRequestId)
      .then((m) => {
        setMatches(m);
        if (m.length > 0 && !lineId) setLineId(m[0].line.id);
      })
      .catch((e) => setError(String(e)));
  }

  useEffect(() => {
    refreshMatches();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [packagingRequestId]);

  function openChooser() {
    setAddMode("choose");
  }

  function openCompose() {
    setAddMode("compose");
    setSelectedComponentIds(new Set());
    setComposeForm(null);
    api
      .listProductionLines()
      .then(setAllLines)
      .catch((e) => setError(String(e)));
  }

  function toggleComponent(id: string) {
    setSelectedComponentIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function proceedToComposeForm() {
    const selected = allLines.filter((l) => selectedComponentIds.has(l.id));
    const derived = deriveCompositeLineDefaults(selected);
    setComposeForm({ ...EMPTY_LINE, ...derived });
  }

  async function handleCreateLine(form: ProductionLineCreate) {
    setAddingLine(true);
    setError(null);
    try {
      const created = await api.createProductionLine(form);
      setAddMode("closed");
      setLineId(created.id);
      refreshMatches();
    } catch (e) {
      setError(String(e));
    } finally {
      setAddingLine(false);
    }
  }

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
            Bu ambalaj türü için uygun bir üretim hattı bulunamadı. Aşağıdan yeni bir üretim hattı ekleyebilirsiniz.
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

      <div className="mt-4">
        {addMode === "closed" && (
          <Button variant="secondary" onClick={openChooser}>
            + Yeni Üretim Hattı Ekle
          </Button>
        )}

        {addMode === "choose" && (
          <Card>
            <CardTitle>Yeni Üretim Hattı Ekle</CardTitle>
            <div className="flex flex-wrap gap-3">
              <Button onClick={openCompose}>Kayıtlı Makineden Hat Oluştur</Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setAddMode("new_machine");
                  setComposeForm(null);
                }}
              >
                Yeni Makine Tanımla
              </Button>
              <Button variant="ghost" onClick={() => setAddMode("closed")}>
                Vazgeç
              </Button>
            </div>
          </Card>
        )}

        {addMode === "new_machine" && (
          <Card>
            <CardTitle subtitle="Bu, /makine-parki sayfasındaki aynı formdur — burada da tek bir yeni makine/hat tanımlayabilirsiniz.">
              Yeni Makine Tanımla
            </CardTitle>
            <MachineForm initial={EMPTY_LINE} submitLabel="Hattı Ekle" submitting={addingLine} onSubmit={handleCreateLine} />
            <Button variant="ghost" className="mt-3" onClick={() => setAddMode("choose")}>
              ← Geri
            </Button>
          </Card>
        )}

        {addMode === "compose" && !composeForm && (
          <Card>
            <CardTitle subtitle="Bir hattı oluşturacak kayıtlı makineleri/üniteleri seçin (ör. Ekstrüder-1 + Gravimetrik Dozaj-1 + Film Hattı-2). Teknik değerler seçilenlerden otomatik türetilecek, submit öncesi düzenleyebilirsiniz.">
              Kayıtlı Makineden Hat Oluştur
            </CardTitle>
            {allLines.length === 0 ? (
              <p className="text-sm text-ink/50">Kayıtlı makine/hat bulunamadı.</p>
            ) : (
              <div className="space-y-2">
                {allLines.map((l) => (
                  <label key={l.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={selectedComponentIds.has(l.id)}
                      onChange={() => toggleComponent(l.id)}
                    />
                    <span className="text-ink/80">{l.name}</span>
                    {l.process_type && <Badge tone="petrol">{l.process_type}</Badge>}
                    <span className="font-mono text-xs text-ink/40">
                      {l.min_micron}-{l.max_micron} µm
                    </span>
                  </label>
                ))}
              </div>
            )}
            <div className="mt-4 flex gap-3">
              <Button onClick={proceedToComposeForm} disabled={selectedComponentIds.size === 0}>
                Devam: Türetilen Değerleri Kontrol Et →
              </Button>
              <Button variant="ghost" onClick={() => setAddMode("choose")}>
                ← Geri
              </Button>
            </div>
          </Card>
        )}

        {addMode === "compose" && composeForm && (
          <Card>
            <CardTitle subtitle="Aşağıdaki değerler seçilen makinelerden otomatik türetildi -- bağlayıcı değildir, submit öncesi düzenleyebilirsiniz.">
              Türetilen Hat Bilgileri
            </CardTitle>
            <MachineForm
              initial={composeForm}
              submitLabel="Hattı Ekle"
              submitting={addingLine}
              onSubmit={handleCreateLine}
            />
            <Button variant="ghost" className="mt-3" onClick={() => setComposeForm(null)}>
              ← Makine Seçimine Dön
            </Button>
          </Card>
        )}
      </div>

      <StageNav currentNo={4} nextEnabled={!!lineId} />
    </div>
  );
}
