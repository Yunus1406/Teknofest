"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import type { ProductionLineOut, ProductionLineCreate } from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EMPTY_LINE, MachineForm } from "@/components/machine-park/MachineForm";

export default function MakineParkiPage() {
  const [lines, setLines] = useState<ProductionLineOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    api
      .listProductionLines()
      .then(setLines)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  async function handleAdd(form: ProductionLineCreate) {
    setAdding(true);
    setError(null);
    try {
      const line = await api.createProductionLine(form);
      setLines((ls) => [...ls, line]);
    } catch (e) {
      setError(String(e));
    } finally {
      setAdding(false);
    }
  }

  async function handleUpdate(id: string, form: ProductionLineCreate) {
    setSavingId(id);
    setError(null);
    try {
      const line = await api.updateProductionLine(id, form);
      setLines((ls) => ls.map((l) => (l.id === id ? line : l)));
      setEditingId(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setSavingId(null);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <p className="text-sm text-ink/60">Yükleniyor…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <p className="font-heading text-sm uppercase tracking-wide text-ink/50">Reçete OS</p>
      <h1 className="mt-1 font-heading text-2xl font-semibold text-ink">Makine Parkı</h1>
      <p className="mt-2 text-sm text-ink/60">
        Firmanın üretim hatları/makineleri — optimizasyon motoru sadece burada kayıtlı hatları kullanır.
      </p>
      <Link href="/asama-1-anasayfa" className="mt-2 inline-block text-sm text-petrol underline underline-offset-2">
        ← Ana Ekrana Dön
      </Link>

      {error && (
        <Card className="mt-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      <CardTitle>
        <span className="mt-8 block">Kayıtlı Makineler ({lines.length})</span>
      </CardTitle>
      {lines.map((line) => (
        <Card key={line.id} className="mb-4">
          {editingId === line.id ? (
            <MachineForm
              initial={line}
              submitLabel="Makineyi Güncelle"
              submitting={savingId === line.id}
              onSubmit={(form) => handleUpdate(line.id, form)}
            />
          ) : (
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-heading text-base font-medium text-ink">{line.name}</span>
                  {line.process_type && <Badge tone="petrol">{line.process_type}</Badge>}
                  {line.availability_status && <Badge tone="neutral">{line.availability_status}</Badge>}
                  {line.component_line_ids && line.component_line_ids.length > 0 && (
                    <Badge tone="regranul">{line.component_line_ids.length} bileşenden oluşturuldu</Badge>
                  )}
                </div>
                <p className="mt-1 text-sm text-ink/60">
                  {line.layer_structure} · {line.min_micron}-{line.max_micron} µm
                  {line.manufacturer ? ` · ${line.manufacturer}` : ""}
                  {line.model ? ` ${line.model}` : ""}
                </p>
              </div>
              <Button variant="secondary" onClick={() => setEditingId(line.id)}>
                Düzenle
              </Button>
            </div>
          )}
        </Card>
      ))}

      <Card>
        <CardTitle>Yeni Makine Ekle</CardTitle>
        <MachineForm initial={EMPTY_LINE} submitLabel="Makineyi Ekle" submitting={adding} onSubmit={handleAdd} />
      </Card>
    </div>
  );
}
