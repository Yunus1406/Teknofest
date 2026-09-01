"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import type {
  BenchmarkReferenceOut,
  CarbonEmissionFactorOut,
  ChemicalRestrictionOut,
  CostReferenceFactorOut,
  FoodContactRequirementOut,
  LayerStructureReferenceOut,
  MechanicalTestStandardOut,
  PolymerOut,
  PolymerTechnicalReferenceOut,
  ProcessReferenceOut,
  RecyclabilityCriterionOut,
  RegulationChangeImpactOut,
  RegulationOut,
  RegulationRequirementOut,
} from "@/lib/types";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { recyclabilityDimensionLabel, referenceDataQualityLabel, referenceDataQualityTone } from "@/lib/labels";

type Category =
  | "carbon"
  | "regulation"
  | "foodContact"
  | "chemical"
  | "polymerTechnical"
  | "mechanicalTest"
  | "process"
  | "layerStructure"
  | "recyclability"
  | "cost"
  | "benchmark";

const CATEGORY_LABEL: Record<Category, string> = {
  carbon: "Karbon",
  regulation: "Mevzuat",
  foodContact: "Gıda Temas",
  chemical: "Kimyasal",
  polymerTechnical: "Polimer Teknik",
  mechanicalTest: "Mekanik Test",
  process: "Proses",
  layerStructure: "Ambalaj Yapısı",
  recyclability: "Geri Dönüştürülebilirlik",
  cost: "Maliyet",
  benchmark: "Benchmark",
};

const CATEGORY_ORDER: Category[] = [
  "carbon",
  "regulation",
  "foodContact",
  "chemical",
  "polymerTechnical",
  "mechanicalTest",
  "process",
  "layerStructure",
  "recyclability",
  "cost",
  "benchmark",
];

function ReferenceRow({
  title,
  subtitle,
  extra,
  source,
  year,
  version,
  isDemoPlaceholder,
}: {
  title: string;
  subtitle?: string | null;
  extra?: string | null;
  source: string | null;
  year: number | null;
  version: string;
  // Bazı kategoriler (ör. RegulationRequirement) bu alanı hiç taşımaz --
  // bilinmeyen bir durumu "Kaynaklı" gibi göstermemek için undefined'da
  // rozet HİÇ render edilmez (uydurma bir onay verilmez).
  isDemoPlaceholder?: boolean;
}) {
  return (
    <div className="border-b border-ink/5 py-3 last:border-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-ink">{title}</p>
          {subtitle && <p className="mt-0.5 text-sm text-ink/60">{subtitle}</p>}
          {extra && <p className="mt-0.5 text-xs text-ink/50">{extra}</p>}
        </div>
        {isDemoPlaceholder !== undefined && (
          <Badge tone={referenceDataQualityTone(isDemoPlaceholder)}>{referenceDataQualityLabel(isDemoPlaceholder)}</Badge>
        )}
      </div>
      <p className="mt-1.5 font-mono text-xs text-ink/40">
        Kaynak: {source ?? "—"} · Yıl: {year ?? "—"} · Versiyon: {version}
      </p>
    </div>
  );
}

function EmptyCategory() {
  return (
    <p className="py-6 text-sm text-ink/50">
      Henüz referans veri girilmedi — bu kategori için gerçek/kaynaklı bir veritabanı entegrasyonu bulunmuyor.
    </p>
  );
}

export default function ReferansMerkeziPage() {
  const [tab, setTab] = useState<Category>("carbon");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [carbon, setCarbon] = useState<CarbonEmissionFactorOut[]>([]);
  const [regulations, setRegulations] = useState<RegulationOut[]>([]);
  const [regulation, setRegulation] = useState<RegulationRequirementOut[]>([]);
  // Faz L.4 (Madde 17) — regulation_id -> etki analizi sonucu (isteğe bağlı,
  // sadece kullanıcı "Etki Analizi" butonuna basınca doldurulur).
  const [impactByRegId, setImpactByRegId] = useState<Record<string, RegulationChangeImpactOut | "loading" | "error">>({});
  const [foodContact, setFoodContact] = useState<FoodContactRequirementOut[]>([]);
  const [chemical, setChemical] = useState<ChemicalRestrictionOut[]>([]);
  const [polymers, setPolymers] = useState<PolymerOut[]>([]);
  const [polymerTechnical, setPolymerTechnical] = useState<PolymerTechnicalReferenceOut[]>([]);
  const [mechanicalTest, setMechanicalTest] = useState<MechanicalTestStandardOut[]>([]);
  const [process, setProcess] = useState<ProcessReferenceOut[]>([]);
  const [layerStructure, setLayerStructure] = useState<LayerStructureReferenceOut[]>([]);
  const [recyclability, setRecyclability] = useState<RecyclabilityCriterionOut[]>([]);
  const [cost, setCost] = useState<CostReferenceFactorOut[]>([]);
  const [benchmark, setBenchmark] = useState<BenchmarkReferenceOut[]>([]);

  useEffect(() => {
    Promise.all([
      api.listCarbonEmissionFactors(),
      api.listRegulations(),
      api.listRegulationRequirements(),
      api.listFoodContactRequirements(),
      api.listChemicalRestrictions(),
      api.listPolymers(),
      api.listPolymerTechnicalReferences(),
      api.listMechanicalTestStandards(),
      api.listProcessReferences(),
      api.listLayerStructureReferences(),
      api.listRecyclabilityCriteria(),
      api.listCostReferenceFactors(),
      api.listBenchmarkReferences(),
    ])
      .then(([c, regs, r, fc, ch, poly, pt, mt, proc, ls, rc, cost_, bm]) => {
        setCarbon(c);
        setRegulations(regs);
        setRegulation(r);
        setFoodContact(fc);
        setChemical(ch);
        setPolymers(poly);
        setPolymerTechnical(pt);
        setMechanicalTest(mt);
        setProcess(proc);
        setLayerStructure(ls);
        setRecyclability(rc);
        setCost(cost_);
        setBenchmark(bm);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const polymerCodeById = new Map(polymers.map((p) => [p.id, p.code]));
  const regulationCodeById = new Map(regulations.map((r) => [r.id, r.code]));

  function fetchImpact(regulationId: string) {
    const code = regulationCodeById.get(regulationId);
    if (!code) return;
    setImpactByRegId((prev) => ({ ...prev, [regulationId]: "loading" }));
    api
      .getRegulationChangeImpact(code)
      .then((result) => setImpactByRegId((prev) => ({ ...prev, [regulationId]: result })))
      .catch(() => setImpactByRegId((prev) => ({ ...prev, [regulationId]: "error" })));
  }

  const counts: Record<Category, number> = {
    carbon: carbon.length,
    regulation: regulation.length,
    foodContact: foodContact.length,
    chemical: chemical.length,
    polymerTechnical: polymerTechnical.length,
    mechanicalTest: mechanicalTest.length,
    process: process.length,
    layerStructure: layerStructure.length,
    recyclability: recyclability.length,
    cost: cost.length,
    benchmark: benchmark.length,
  };

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
      <h1 className="mt-1 font-heading text-2xl font-semibold text-ink">Referans Merkezi</h1>
      <p className="mt-2 text-sm text-ink/60">
        Sistemde kullanılan her karbon faktörü, mevzuat eşiği, mekanik limit ve tipik değerin kaynağı burada —
        her satır kaynak/yıl/versiyon bilgisiyle listelenir. Kaynaksız hiçbir rakam yoktur: gerçek bir kaynağı
        olmayan her değer açıkça &quot;DEMO / VARSAYIMSAL&quot; etiketi taşır.
      </p>
      <Link href="/asama-1-anasayfa" className="mt-2 inline-block text-sm text-petrol underline underline-offset-2">
        ← Ana Ekrana Dön
      </Link>

      {error && (
        <Card className="mt-6 border-warn/30 bg-warn/5">
          <p className="text-sm text-warn">{error}</p>
        </Card>
      )}

      <div className="mt-8 flex flex-wrap gap-2 border-b border-ink/10">
        {CATEGORY_ORDER.map((c) => (
          <button
            key={c}
            onClick={() => setTab(c)}
            className={`px-3 py-2 text-sm font-medium ${
              tab === c ? "border-b-2 border-petrol text-petrol" : "text-ink/50 hover:text-ink"
            }`}
          >
            {CATEGORY_LABEL[c]} ({counts[c]})
          </button>
        ))}
      </div>

      <Card className="mt-6">
        <CardTitle>{CATEGORY_LABEL[tab]}</CardTitle>

        {tab === "carbon" &&
          (carbon.length === 0 ? (
            <EmptyCategory />
          ) : (
            <div>
              {carbon.map((r) => (
                <ReferenceRow
                  key={r.id}
                  title={r.material_key}
                  subtitle={`${r.factor_type} · ${r.ef_value} ${r.unit}`}
                  extra={r.geography ? `Coğrafya: ${r.geography}` : null}
                  source={r.source}
                  year={r.year}
                  version={r.version ?? "—"}
                  isDemoPlaceholder={r.is_demo_placeholder}
                />
              ))}
            </div>
          ))}

        {tab === "regulation" &&
          (regulation.length === 0 ? (
            <EmptyCategory />
          ) : (
            <div>
              {regulation.map((r) => {
                const extraParts: string[] = [];
                if (r.threshold_value != null) {
                  extraParts.push(`Eşik: %${r.threshold_value} ${r.threshold_unit ?? ""}${r.target_year ? ` (${r.target_year})` : ""}`);
                }
                if (r.packaging_category) extraParts.push(`Kategori: ${r.packaging_category}`);
                if (r.exception_text) extraParts.push(`İstisna: ${r.exception_text}`);
                extraParts.push(`Uygulanma Tarihi: ${r.effective_date ? new Date(r.effective_date).toLocaleDateString("tr-TR") : "Belirtilmedi"}`);
                extraParts.push(`Son Güncelleme: ${r.last_reviewed_at ? new Date(r.last_reviewed_at).toLocaleDateString("tr-TR") : "Belirtilmedi"}`);
                // Faz L.3 — SADECE gerçekten bir değişiklik tespit edildiyse
                // (loader'ın snapshot karşılaştırması) görünür.
                if (r.change_summary) {
                  extraParts.push(
                    `Önceki Sürüm: ${r.previous_version ?? "—"} (${r.change_summary})${r.changed_at ? ` — ${new Date(r.changed_at).toLocaleDateString("tr-TR")}` : ""}`
                  );
                }
                const impact = impactByRegId[r.regulation_id];
                return (
                  <div key={r.id}>
                    <ReferenceRow
                      title={`${r.regulation_no} — ${r.article}${r.sub_article ? ` (${r.sub_article})` : ""}`}
                      subtitle={r.requirement_text}
                      extra={extraParts.join(" · ")}
                      source={r.source}
                      year={r.target_year}
                      version={r.version}
                    />
                    {/* Faz L.4 (Madde 17) — mevzuat değişiklik etki analizi,
                        talep üzerine (buton) hesaplanır -- her satırda otomatik
                        tetiklenmez, gereksiz sorgu yapılmaz. */}
                    {regulationCodeById.has(r.regulation_id) && (
                      <div className="-mt-2 mb-2 pl-1">
                        <button
                          type="button"
                          className="text-xs font-medium text-petrol hover:underline"
                          onClick={() => fetchImpact(r.regulation_id)}
                          disabled={impact === "loading"}
                        >
                          {impact === "loading" ? "Analiz ediliyor…" : "Etki Analizi"}
                        </button>
                        {impact && impact !== "loading" && impact !== "error" && (
                          <p className="mt-1 text-xs text-ink/60">
                            ⚠ {impact.total_active_skus} aktif SKU incelendi. {impact.affected_sku_count} ürün
                            değişiklikten etkileniyor. {impact.evidence_needed_count} ürün için yeni kanıt gerekli.{" "}
                            {impact.recipe_reassessment_count} reçete yeniden değerlendirilmelidir.
                            {impact.affected_sku_codes.length > 0 && ` (${impact.affected_sku_codes.join(", ")})`}
                          </p>
                        )}
                        {impact === "error" && <p className="mt-1 text-xs text-warn">Analiz alınamadı.</p>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}

        {tab === "foodContact" &&
          (foodContact.length === 0 ? (
            <EmptyCategory />
          ) : (
            <div>
              {foodContact.map((r) => (
                <ReferenceRow
                  key={r.id}
                  title={r.requirement_type}
                  subtitle={r.notes ?? (r.limit_value != null ? `Limit: ${r.limit_value} ${r.limit_unit}` : null)}
                  extra={r.applies_to_pcr ? "PCR'a özgü ek gereklilik" : null}
                  source={r.source}
                  year={r.year}
                  version={r.version}
                  isDemoPlaceholder={r.is_demo_placeholder}
                />
              ))}
            </div>
          ))}

        {tab === "chemical" &&
          (chemical.length === 0 ? (
            <EmptyCategory />
          ) : (
            <div>
              {chemical.map((r) => (
                <ReferenceRow
                  key={r.id}
                  title={`${r.substance_group} — ${r.restriction_type}`}
                  subtitle={`≤${r.limit_value} ${r.limit_unit}`}
                  extra={r.food_contact_only ? "Sadece gıda temaslı ambalajlarda uygulanır" : null}
                  source={r.source}
                  year={r.year}
                  version={r.version}
                  isDemoPlaceholder={r.is_demo_placeholder}
                />
              ))}
            </div>
          ))}

        {tab === "polymerTechnical" &&
          (polymerTechnical.length === 0 ? (
            <EmptyCategory />
          ) : (
            <div>
              {polymerTechnical.map((r) => (
                <ReferenceRow
                  key={r.id}
                  title={`${polymerCodeById.get(r.polymer_id) ?? "?"} — ${r.property_name}`}
                  subtitle={
                    r.typical_min != null && r.typical_max != null ? `${r.typical_min}–${r.typical_max} ${r.unit}` : null
                  }
                  source={r.source}
                  year={r.year}
                  version={r.version}
                  isDemoPlaceholder={r.is_demo_placeholder}
                />
              ))}
            </div>
          ))}

        {tab === "mechanicalTest" &&
          (mechanicalTest.length === 0 ? (
            <EmptyCategory />
          ) : (
            <div>
              {mechanicalTest.map((r) => (
                <ReferenceRow
                  key={r.id}
                  title={`${r.test_type} (${r.standard_name})`}
                  subtitle={
                    r.typical_min != null && r.typical_max != null ? `${r.typical_min}–${r.typical_max} ${r.unit}` : null
                  }
                  extra={r.packaging_category ? `Kategori: ${r.packaging_category}` : "Tüm kategoriler için geçerli"}
                  source={r.source}
                  year={r.year}
                  version={r.version}
                  isDemoPlaceholder={r.is_demo_placeholder}
                />
              ))}
            </div>
          ))}

        {tab === "process" &&
          (process.length === 0 ? (
            <EmptyCategory />
          ) : (
            <div>
              {process.map((r) => (
                <ReferenceRow
                  key={r.id}
                  title={`${r.process_type} — ${r.parameter_name}`}
                  subtitle={
                    r.typical_min != null && r.typical_max != null ? `${r.typical_min}–${r.typical_max} ${r.unit}` : null
                  }
                  source={r.source}
                  year={r.year}
                  version={r.version}
                  isDemoPlaceholder={r.is_demo_placeholder}
                />
              ))}
            </div>
          ))}

        {tab === "layerStructure" &&
          (layerStructure.length === 0 ? (
            <EmptyCategory />
          ) : (
            <div>
              {layerStructure.map((r) => (
                <ReferenceRow
                  key={r.id}
                  title={r.structure_pattern}
                  subtitle={r.typical_usage}
                  extra={r.barrier_properties}
                  source={r.source}
                  year={r.year}
                  version={r.version}
                  isDemoPlaceholder={r.is_demo_placeholder}
                />
              ))}
            </div>
          ))}

        {tab === "recyclability" &&
          (recyclability.length === 0 ? (
            <EmptyCategory />
          ) : (
            <div>
              {recyclability.map((r) => (
                <ReferenceRow
                  key={r.id}
                  title={recyclabilityDimensionLabel(r.dimension)}
                  subtitle={r.criterion_text}
                  extra={r.weight_pct != null ? `Temsili ağırlık: %${r.weight_pct}` : null}
                  source={r.source}
                  year={r.year}
                  version={r.version}
                  isDemoPlaceholder={r.is_demo_placeholder}
                />
              ))}
            </div>
          ))}

        {tab === "cost" &&
          (cost.length === 0 ? (
            <EmptyCategory />
          ) : (
            <div>
              {cost.map((r) => (
                <ReferenceRow
                  key={r.id}
                  title={r.cost_type}
                  subtitle={
                    r.typical_min != null && r.typical_max != null
                      ? `${r.typical_min}–${r.typical_max} ${r.unit} (${r.currency})`
                      : null
                  }
                  extra={r.geography ? `Coğrafya: ${r.geography}` : null}
                  source={r.source}
                  year={r.year}
                  version={r.version}
                  isDemoPlaceholder={r.is_demo_placeholder}
                />
              ))}
            </div>
          ))}

        {tab === "benchmark" &&
          (benchmark.length === 0 ? (
            <EmptyCategory />
          ) : (
            <div>
              {benchmark.map((r) => (
                <ReferenceRow
                  key={r.id}
                  title={r.metric_name}
                  subtitle={r.typical_value != null ? `${r.typical_value} ${r.unit}` : null}
                  extra={r.packaging_category ? `Kategori: ${r.packaging_category}` : null}
                  source={r.source}
                  year={r.year}
                  version={r.version}
                  isDemoPlaceholder={r.is_demo_placeholder}
                />
              ))}
            </div>
          ))}
      </Card>
    </div>
  );
}
