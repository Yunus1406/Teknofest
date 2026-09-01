"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { LineMatchOut, ProductionLineCreate, ProductionLineOut } from "@/lib/types";
import { ActiveCaseSummary } from "@/components/layout/ActiveCaseSummary";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EMPTY_LINE, MachineForm } from "@/components/machine-park/MachineForm";
import { deriveCompositeLineDefaults } from "@/lib/line-composition";
import { matchCriterionLabel } from "@/lib/labels";
import { useCaseStore } from "@/stores/case-store";

type AddMode = "closed" | "choose" | "compose" | "new_machine";

export default function Stage4Page() {
  const packagingRequestId = useCaseStore((s) => s.packagingRequestId);
  const lineId = useCaseStore((s) => s.lineId);
  const lineEligible = useCaseStore((s) => s.lineEligible);
  const setLineId = useCaseStore((s) => s.setLineId);
  const setLineEligible = useCaseStore((s) => s.setLineEligible);

  const [matches, setMatches] = useState<LineMatchOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);

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
        // Faz K.3 — burada `lineId`'nin render kapanışındaki (stale
        // olabilecek) değeri DEĞİL, store'un o ANki gerçek değeri okunur;
        // aksi halde kullanıcı listede ilk olmayan bir hattı seçtiğinde,
        // henüz yenilenmemiş eski `lineId` kapanışı "seçili hat yok"
        // sanıp seçimi sessizce ilk eşleşen hatla EZEBİLİRDİ.
        // Faz K.4 — `m` artık uygun OLMAYAN hatları da içerebilir; otomatik
        // seçim SADECE gerçekten uygun (`eligible`) bir hat için yapılmalı.
        const firstEligible = m.find((match) => match.eligible);
        const currentLineId = useCaseStore.getState().lineId;
        if (firstEligible && !currentLineId) {
          setLineId(firstEligible.line.id);
          setLineEligible(true);
        } else if (currentLineId) {
          // Faz K.8 — `lineEligible`, seçili hattın K.4'ün en GÜNCEL
          // eşleştirme sonucuna göre gerçekten uygun olup olmadığıyla
          // senkron tutulur (yeni hat oluşturma dahil, her refreshMatches
          // çağrısında yeniden değerlendirilir) -- Aşama 5/6 gate'i buna bakar.
          const currentMatch = m.find((match) => match.line.id === currentLineId);
          setLineEligible(currentMatch?.eligible ?? false);
        }
      })
      .catch((e) => setError(String(e)));
  }

  // Faz K.3 (Madde 5) — Kullanıcı bir hat seçtiğinde ("Ekle" yerine radio
  // seçimi) hem görünür bir onay verilmeli hem de eşleştirme otomatik
  // yeniden hesaplanmalı; önceden state güncelleniyordu ama HİÇBİR görsel
  // geri bildirim yoktu, kullanıcı "hiçbir şey olmadı" sanıyordu.
  function selectLine(id: string, name: string) {
    setLineId(id);
    setConfirmation(`${name} çalışmaya başarıyla eklendi.`);
    refreshMatches();
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
      setConfirmation(`${created.name} çalışmaya başarıyla eklendi.`);
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
      <ActiveCaseSummary />

      {error && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      {confirmation && (
        <Card className="mb-4 border-pcr/30 bg-pcr/5">
          <p className="text-sm text-pcr">✓ {confirmation}</p>
        </Card>
      )}

      {matches && matches.every((m) => !m.eligible) && (
        <Card className="border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">
            {matches.length === 0
              ? "Kayıtlı hiçbir aktif üretim hattı yok."
              : "Bu ambalaj türü için tam uygun bir üretim hattı bulunamadı — aşağıda en yakın adaylar ve eksik kriterleri listeleniyor."}
            {" "}Aşağıdan yeni bir üretim hattı ekleyebilirsiniz.
          </p>
        </Card>
      )}

      <div className="space-y-3">
        {matches?.map((m) => (
          <Card
            key={m.line.id}
            className={`transition-colors ${m.eligible ? "cursor-pointer" : "opacity-70"} ${
              lineId === m.line.id ? "border-petrol/50 ring-1 ring-petrol/30" : ""
            }`}
          >
            <label className={`flex items-start gap-3 ${m.eligible ? "cursor-pointer" : "cursor-not-allowed"}`}>
              <input
                type="radio"
                className="mt-1"
                checked={lineId === m.line.id}
                disabled={!m.eligible}
                onChange={() => selectLine(m.line.id, m.line.name)}
              />
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <CardTitle>{m.line.name}</CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge tone={m.eligible ? "pcr" : "warn"}>%{m.score_pct} uyumlu</Badge>
                    <Badge tone="petrol">{m.line.layer_structure}</Badge>
                  </div>
                </div>
                <p className={`text-sm ${m.eligible ? "text-ink/60" : "text-warn"}`}>{m.match_reason}</p>
                {m.criteria && (
                  <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 font-mono text-xs">
                    {Object.entries(m.criteria).map(([key, ok]) => (
                      <span key={key} className={ok ? "text-pcr" : "text-warn"}>
                        {ok ? "✓" : "✕"} {matchCriterionLabel(key)}
                        {/* Faz N.1b (Madde 14) — hedef kalınlık girilmemişse
                            bu kriter değerlendirilmiyor, "geçti" VARSAYILIYOR;
                            bu artık kullanıcıya açıkça belirtilir. */}
                        {key === "mikron_araligi" && m.mikron_araligi_veri_guveni === "varsayimsal" && (
                          <span className="ml-0.5 text-ink/40" title="Hedef kalınlık girilmediği için bu kriter değerlendirilmedi, geçti varsayıldı.">
                            (varsayımsal)
                          </span>
                        )}
                      </span>
                    ))}
                  </div>
                )}
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

      {/* Faz K.8 — `!!lineId` TEK BAŞINA yetmez: kullanıcı "Yeni Üretim
          Hattı Ekle" ile uyumsuz bir hat da oluşturabilir. Sonraki aşamaya
          geçiş SADECE K.4'ün onayladığı (`lineEligible`) bir hat için açılır. */}
      <StageNav currentNo={4} nextEnabled={!!lineId && lineEligible} />
    </div>
  );
}
