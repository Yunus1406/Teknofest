"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import type { PhysicalTestIn, PhysicalVerificationResultOut, SuggestedTestTargetOut } from "@/lib/types";
import { ActiveCaseSummary } from "@/components/layout/ActiveCaseSummary";
import { StageHeader } from "@/components/layout/StageHeader";
import { StageNav } from "@/components/layout/StageNav";
import { Card, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import {
  dataConfidenceFromSourceKind,
  dataConfidenceLabel,
  dataConfidenceTone,
  physicalTestResultLabel,
  physicalTestResultTone,
} from "@/lib/labels";
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
      <ActiveCaseSummary />

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
                {(() => {
                  // Faz I.4 — hedef aralığının GERÇEK kaynağı: backend'in
                  // `target_source`'u (Mekanik Test Kabul Kriterleri) varsa
                  // önce o kullanılır ("kullanici_girisi" → Yüksek); yoksa
                  // F.6 referans önerisi varsa Sistem Referansı (Düşük);
                  // hiçbiri yoksa rozet yok. Kullanıcı girdisi artık asla
                  // "Hesaplanan" diye yanlış etiketlenmez.
                  const kind = s?.target_source ?? (s?.suggestion_source ? "sistem_referansi" : null);
                  const level = dataConfidenceFromSourceKind(kind);
                  if (!level) return null;
                  return (
                    <Badge tone={dataConfidenceTone(level)}>{dataConfidenceLabel(level)}</Badge>
                  );
                })()}
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
        <>
          <Card className="mt-4">
            <CardTitle>Test Sonucu Detayı</CardTitle>
            <ul className="space-y-1.5">
              {result.results.map((r) => (
                <li key={r.id} className="flex items-center gap-2 text-sm">
                  <span className="text-ink/70">{TEST_LABELS[r.test_type] ?? r.test_type}</span>
                  <Badge tone={physicalTestResultTone(r.result)}>{physicalTestResultLabel(r.result)}</Badge>
                </li>
              ))}
            </ul>
          </Card>

          <Card
            className={`mt-4 ${
              result.all_passed
                ? "border-pcr/30 bg-pcr/5"
                : result.new_recipe_version
                  ? "border-warn/30 bg-warn/5"
                  : "border-virgin/30 bg-virgin/5"
            }`}
          >
            {result.all_passed ? (
              <>
                <Badge tone="pcr">Tüm testler başarılı</Badge>
                <p className="mt-2 text-sm text-ink/70">
                  Reçete doğrulandı. Nihai sonuç ve sürdürülebilirlik kazanımı için sonraki aşamaya geçebilirsiniz.
                </p>
              </>
            ) : result.new_recipe_version ? (
              <>
                <Badge tone="warn">Bir veya daha fazla test hedefin dışında</Badge>
                <p className="mt-2 text-sm text-ink/70">
                  Reçete <span className="font-mono">V{result.new_recipe_version.version}</span> olarak yeni bir
                  versiyona alındı ve optimizasyona geri döndü. Önceki versiyon (
                  <span className="font-mono">V{result.new_recipe_version.version - 1}</span>) geçmişte saklanıyor.
                </p>
                <Button className="mt-3" variant="secondary" onClick={handleContinueWithNewVersion}>
                  Yeni Versiyonla Devam Et
                </Button>
              </>
            ) : (
              <>
                <Badge tone="virgin">Doğrulama Bekleniyor</Badge>
                <p className="mt-2 text-sm text-ink/70">
                  Hiçbir test hedef aralığın dışında değil, ama bir veya daha fazla test için bilgi tabanında
                  tanımlı bir kabul kriteri yok — bu bir reçete kusuru değil, veri boşluğu. Kriter tanımlanana
                  kadar reçete &quot;Doğrulandı&quot; sayılamaz.
                </p>
              </>
            )}
          </Card>
        </>
      )}

      <StageNav currentNo={11} nextEnabled={!!result?.all_passed} />
    </div>
  );
}
