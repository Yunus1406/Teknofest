"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { PhysicalTestIn, PhysicalVerificationResultOut, SuggestedTestTargetOut } from "@/lib/types";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useCaseStore } from "@/stores/case-store";

const TEST_LABELS: Record<string, string> = {
  kalinlik: "Kalınlık",
  gramaj: "Gramaj (alansal, g/m²)",
  tensile: "Tensile (Çekme Dayanımı)",
  elongation: "Elongation (Uzama)",
  dart_impact: "Dart Impact (Düşürme Darbesi)",
  tear: "Tear (Yırtılma)",
  seal: "Seal (Kaynak Dayanımı)",
};

export default function Stage11Page() {
  const productionOrderId = useCaseStore((s) => s.productionOrderId);
  const recipeId = useCaseStore((s) => s.recipeId);
  const setRecipeId = useCaseStore((s) => s.setRecipeId);

  const [suggested, setSuggested] = useState<SuggestedTestTargetOut[] | null>(null);
  const [tests, setTests] = useState<PhysicalTestIn[]>([]);
  const [result, setResult] = useState<PhysicalVerificationResultOut | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!recipeId) return;
    api
      .getSuggestedTestTargets(recipeId)
      .then((targets) => {
        setSuggested(targets);
        setTests(
          targets.map((t) => ({
            test_type: t.test_type,
            value: t.nominal_value ?? 0,
            unit: t.unit,
            target_min: t.target_min,
            target_max: t.target_max,
            test_method: t.test_method,
          }))
        );
      })
      .catch((e) => setError(String(e)));
  }, [recipeId]);

  function updateValue(idx: number, value: number) {
    setTests((t) => t.map((row, i) => (i === idx ? { ...row, value } : row)));
  }

  async function handleSubmit() {
    if (!productionOrderId) return;
    setSubmitting(true);
    setError(null);
    try {
      const r = await api.submitPhysicalVerification(productionOrderId, tests);
      setResult(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  function handleContinueWithNewVersion() {
    if (result?.new_recipe_version) {
      setRecipeId(result.new_recipe_version.id);
    }
  }

  const suggestedByType = Object.fromEntries((suggested ?? []).map((t) => [t.test_type, t]));

  return (
    <div>
      <StageHeader
        no={11}
        title="Fiziksel Doğrulama"
        description="Üretilen ambalajın test sonuçları girilir/onaylanır. Hedefler, reçetenin gerçek kalınlığından türetilir. Başarısızsa reçete yeni versiyon olarak (V1→V2) optimizasyona geri döner; tüm geçmiş saklanır."
      />

      {error && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}
      {!recipeId && (
        <Card className="mb-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">Önce bir reçete seçilmeli (Aşama 7-9).</p>
        </Card>
      )}

      <Card>
        <CardTitle subtitle="Kalınlık/gramaj hedefleri reçeteden otomatik türetildi; mekanik testler için bilgi tabanında malzeme verisi olmadığından hedef önerilmiyor — laboratuvar/şartname referansına göre elle girin.">
          Test Sonuçları
        </CardTitle>
        <div className="space-y-4">
          {tests.map((t, i) => {
            const s = suggestedByType[t.test_type];
            return (
              <div key={t.test_type} className="border-b border-ink/5 pb-3 last:border-0">
                <div className="grid grid-cols-[1fr_auto_auto] items-center gap-3">
                  <span className="text-sm text-ink/70">{TEST_LABELS[t.test_type] ?? t.test_type}</span>
                  <input
                    type="number"
                    step="any"
                    className="w-28 rounded-lg border border-ink/15 bg-white/70 px-2 py-1.5 text-sm font-mono"
                    value={t.value}
                    onChange={(e) => updateValue(i, Number(e.target.value))}
                  />
                  <span className="font-mono text-xs text-ink/40">
                    {t.unit} (hedef: {t.target_min ?? "—"}–{t.target_max ?? "—"})
                  </span>
                </div>
                {s && <p className="mt-1 text-xs text-ink/40">{s.note}</p>}
                {t.test_method && (
                  <p className="mt-0.5 text-xs text-ink/40">
                    Yöntem/Standart: <span className="text-ink/60">{t.test_method}</span>
                  </p>
                )}
              </div>
            );
          })}
        </div>
        <Button className="mt-5" onClick={handleSubmit} disabled={submitting || !productionOrderId || !!result || tests.length === 0}>
          {submitting ? "Gönderiliyor…" : result ? "Gönderildi ✓" : "Test Sonuçlarını Onayla"}
        </Button>
      </Card>

      {result && (
        <Card className={`mt-4 ${result.all_passed ? "border-pcr/30 bg-pcr/5" : "border-warn/30 bg-warn/5"}`}>
          {result.all_passed ? (
            <>
              <Badge tone="pcr">Tüm testler başarılı</Badge>
              <p className="mt-2 text-sm text-ink/70">
                Reçete doğrulandı. Nihai sonuç ve sürdürülebilirlik kazanımı için sonraki aşamaya geçebilirsiniz.
              </p>
            </>
          ) : (
            <>
              <Badge tone="warn">Bir veya daha fazla test hedefin dışında</Badge>
              <p className="mt-2 text-sm text-ink/70">
                Reçete <span className="font-mono">V{result.new_recipe_version?.version}</span> olarak yeni bir
                versiyona alındı ve optimizasyona geri döndü. Önceki versiyon (
                <span className="font-mono">V{result.new_recipe_version?.version ? result.new_recipe_version.version - 1 : "?"}</span>
                ) geçmişte saklanıyor.
              </p>
              <Button className="mt-3" variant="secondary" onClick={handleContinueWithNewVersion}>
                Yeni Versiyonla Devam Et
              </Button>
            </>
          )}
        </Card>
      )}

      <StageNav currentNo={11} nextEnabled={!!result?.all_passed} />
    </div>
  );
}
