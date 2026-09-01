import type {
  AdditiveCreate,
  AdditiveOut,
  AdditiveUpdate,
  BenchmarkReferenceOut,
  CarbonEmissionFactorOut,
  ChemicalRestrictionOut,
  CompanyCreate,
  CompanyProfileOut,
  CompanyUpdate,
  ComparisonOut,
  CostReferenceFactorOut,
  DashboardSummaryOut,
  DigitalProductPassportOut,
  FacilityOut,
  FacilityUpsert,
  FinalResultOut,
  FoodContactRequirementOut,
  LayerStructureReferenceOut,
  LineMatchOut,
  MaterialCreate,
  MaterialOut,
  MaterialUpdate,
  MechanicalTestStandardOut,
  OptimizationRunOut,
  PolymerOut,
  PolymerTechnicalReferenceOut,
  PackagingRequestCreate,
  PackagingRequestOut,
  PhysicalTestIn,
  PhysicalVerificationResultOut,
  ProcessReferenceOut,
  ProductionLiveDataOut,
  ProductionLineCreate,
  ProductionLineOut,
  ProductionLineUpdate,
  ProductionOrderOut,
  ProductionOrderSummaryOut,
  ProductSkuCreate,
  ProductSkuDetailOut,
  ProductSkuOut,
  ProductSkuUpdate,
  RecipeOut,
  RecyclabilityCriterionOut,
  RegulationChangeImpactOut,
  RegulationOut,
  RegulationRequirementOut,
  RegulatoryAssessmentSummaryOut,
  SpecExtractionOut,
  SuggestedTestTargetOut,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** `status` alanı sayesinde çağıranlar (ör. Aşama 10) "bu ID artık backend'de
 * yok" (404) durumunu, ağ hatası gibi diğer hatalardan ayırt edip devam eden
 * bir kurtarma akışı (stale ID'yi temizle, kullanıcıyı geri yönlendir)
 * sunabilir — düz `Error` ile bunu güvenilir yakalamak metin ayrıştırmayı
 * gerektirirdi. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}/api/v1${path}`, {
    ...init,
    headers: { ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* yanıt JSON değil */
    }
    throw new ApiError(res.status, `API hatası (${res.status}): ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Aşama 1
  getDashboardSummary: () => request<DashboardSummaryOut>("/dashboard1/summary"),

  // Bilgi Tabanı
  listRegulations: () => request<RegulationOut[]>("/kb/regulations"),
  // Faz L.4 (Madde 17)
  getRegulationChangeImpact: (code: string) =>
    request<RegulationChangeImpactOut>(`/kb/regulations/${encodeURIComponent(code)}/change-impact`),
  listPolymers: () => request<PolymerOut[]>("/kb/polymers"),
  listMaterials: () => request<MaterialOut[]>("/kb/materials"),
  listAdditives: () => request<AdditiveOut[]>("/kb/additives"),
  listCarbonEmissionFactors: () => request<CarbonEmissionFactorOut[]>("/kb/carbon-emission-factors"),
  listProductionLines: () => request<ProductionLineOut[]>("/kb/production-lines"),
  listProductSkus: () => request<ProductSkuOut[]>("/product-skus"),
  getProductSkuDetail: (skuId: string) => request<ProductSkuDetailOut>(`/product-skus/${skuId}/detail`),
  createProductSku: (payload: ProductSkuCreate) =>
    request<ProductSkuOut>("/product-skus", { method: "POST", body: JSON.stringify(payload) }),
  updateProductSku: (skuId: string, payload: ProductSkuUpdate) =>
    request<ProductSkuOut>(`/product-skus/${skuId}`, { method: "PUT", body: JSON.stringify(payload) }),

  // Aşama 2
  createPackagingRequest: (payload: PackagingRequestCreate) =>
    request<PackagingRequestOut>("/packaging-flow/requests", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getPackagingRequest: (id: string) => request<PackagingRequestOut>(`/packaging-flow/requests/${id}`),
  updatePackagingRequest: (id: string, payload: PackagingRequestCreate) =>
    request<PackagingRequestOut>(`/packaging-flow/requests/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  extractSpecFromText: (id: string, specText: string) => {
    const form = new FormData();
    form.set("spec_text", specText);
    return request<SpecExtractionOut>(`/packaging-flow/requests/${id}/spec-extraction`, {
      method: "POST",
      body: form,
    });
  },
  extractSpecFromFile: (id: string, file: File) => {
    const form = new FormData();
    form.set("file", file);
    return request<SpecExtractionOut>(`/packaging-flow/requests/${id}/spec-extraction`, {
      method: "POST",
      body: form,
    });
  },

  // Aşama 3
  runRegulatoryAssessment: (requestId: string) =>
    request<RegulatoryAssessmentSummaryOut>(`/packaging-flow/requests/${requestId}/regulatory-assessment`, {
      method: "POST",
    }),

  // Aşama 4
  getInfrastructureMatches: (requestId: string) =>
    request<LineMatchOut[]>(`/packaging-flow/requests/${requestId}/infrastructure-matches`),

  // Aşama 5
  generateInitialRecipe: (requestId: string, lineId: string) =>
    request<RecipeOut>(`/packaging-flow/requests/${requestId}/initial-recipe?line_id=${lineId}`, {
      method: "POST",
    }),

  // Aşama 6-7
  runOptimization: (requestId: string, lineId: string, ratioStepPct = 10) =>
    request<OptimizationRunOut>(
      `/optimization/requests/${requestId}/run?line_id=${lineId}&ratio_step_pct=${ratioStepPct}`,
      { method: "POST" }
    ),
  getOptimizationRun: (runId: string) => request<OptimizationRunOut>(`/optimization/runs/${runId}`),

  getRecipe: (recipeId: string) => request<RecipeOut>(`/production-flow/recipes/${recipeId}`),

  // Aşama 8
  getComparison: (recipeId: string) => request<ComparisonOut>(`/production-flow/recipes/${recipeId}/comparison`),

  // Aşama 9
  createProductionOrder: (recipeId: string, qtyUnits: number, approvedBy: string) =>
    request<ProductionOrderOut>(
      `/production-flow/recipes/${recipeId}/production-orders?qty_units=${qtyUnits}&approved_by=${encodeURIComponent(approvedBy)}`,
      { method: "POST" }
    ),
  getProductionOrderSummary: (orderId: string) =>
    request<ProductionOrderSummaryOut>(`/production-flow/production-orders/${orderId}/summary`),

  // Aşama 10
  simulateLiveData: (orderId: string) =>
    request<ProductionLiveDataOut[]>(`/production-flow/production-orders/${orderId}/simulate-live-data`, {
      method: "POST",
    }),

  // Aşama 11
  getSuggestedTestTargets: (recipeId: string) =>
    request<SuggestedTestTargetOut[]>(`/production-flow/recipes/${recipeId}/suggested-test-targets`),
  submitPhysicalVerification: (orderId: string, tests: PhysicalTestIn[]) =>
    request<PhysicalVerificationResultOut>(`/production-flow/physical-verification`, {
      method: "POST",
      body: JSON.stringify({ production_order_id: orderId, tests }),
    }),

  // Aşama 12
  finalizeResult: (recipeId: string) =>
    request<FinalResultOut>(`/production-flow/recipes/${recipeId}/finalize`, { method: "POST" }),

  // Faz C.1/C.2 — Dijital Ürün Pasaportu
  createOrGetPassport: (recipeId: string) =>
    request<DigitalProductPassportOut>("/passports", {
      method: "POST",
      body: JSON.stringify({ recipe_id: recipeId }),
    }),
  getPassport: (passportNo: string, authorizedKey?: string) =>
    request<DigitalProductPassportOut>(
      `/passports/${passportNo}${authorizedKey ? `?authorized_key=${encodeURIComponent(authorizedKey)}` : ""}`
    ),

  // Faz C.5-C.7 — Otomatik Optimizasyon Raporu (PDF indirme). JSON dönmediği
  // için `request()` yerine ham `fetch` + blob kullanılır; tarayıcı indirmesi
  // geçici bir <a download> öğesiyle tetiklenir (yeni sekme/pencere gerekmez).
  downloadOptimizationReport: async (recipeId: string, format: "technical" | "executive") => {
    const res = await fetch(
      `${BASE_URL}/api/v1/production-flow/recipes/${recipeId}/optimization-report?format=${format}`,
      { cache: "no-store" }
    );
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail ?? JSON.stringify(body);
      } catch {
        /* yanıt JSON değil */
      }
      throw new ApiError(res.status, `API hatası (${res.status}): ${detail}`);
    }
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") ?? "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : `optimizasyon-raporu-${format}.pdf`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },

  // Faz E.1 — Firma Profili (tek kiracılı: Company yoksa getProfile 404 atar)
  getCompanyProfile: () => request<CompanyProfileOut>("/company/profile"),
  createCompanyProfile: (payload: CompanyCreate) =>
    request<CompanyProfileOut>("/company/profile", { method: "POST", body: JSON.stringify(payload) }),
  updateCompanyProfile: (payload: CompanyUpdate) =>
    request<CompanyProfileOut>("/company/profile", { method: "PUT", body: JSON.stringify(payload) }),
  createFacility: (payload: FacilityUpsert) =>
    request<FacilityOut>("/company/facilities", { method: "POST", body: JSON.stringify(payload) }),
  updateFacility: (facilityId: string, payload: FacilityUpsert) =>
    request<FacilityOut>(`/company/facilities/${facilityId}`, { method: "PUT", body: JSON.stringify(payload) }),

  // Faz E.2 — Makine Parkı
  createProductionLine: (payload: ProductionLineCreate) =>
    request<ProductionLineOut>("/production-lines", { method: "POST", body: JSON.stringify(payload) }),
  updateProductionLine: (lineId: string, payload: ProductionLineUpdate) =>
    request<ProductionLineOut>(`/production-lines/${lineId}`, { method: "PUT", body: JSON.stringify(payload) }),

  // Faz E.3 — Hammadde ve Malzeme Kütüphanesi
  createMaterial: (payload: MaterialCreate) =>
    request<MaterialOut>("/materials", { method: "POST", body: JSON.stringify(payload) }),
  updateMaterial: (materialId: string, payload: MaterialUpdate) =>
    request<MaterialOut>(`/materials/${materialId}`, { method: "PUT", body: JSON.stringify(payload) }),
  createAdditive: (payload: AdditiveCreate) =>
    request<AdditiveOut>("/additives", { method: "POST", body: JSON.stringify(payload) }),
  updateAdditive: (additiveId: string, payload: AdditiveUpdate) =>
    request<AdditiveOut>(`/additives/${additiveId}`, { method: "PUT", body: JSON.stringify(payload) }),

  // Faz F.13 — Referans Merkezi Ekranı (salt okunur /reference/* uçları)
  listRegulationRequirements: () => request<RegulationRequirementOut[]>("/reference/regulation-requirements"),
  listChemicalRestrictions: () => request<ChemicalRestrictionOut[]>("/reference/chemical-restrictions"),
  listFoodContactRequirements: () => request<FoodContactRequirementOut[]>("/reference/food-contact-requirements"),
  listPolymerTechnicalReferences: () => request<PolymerTechnicalReferenceOut[]>("/reference/polymer-technical"),
  listMechanicalTestStandards: () => request<MechanicalTestStandardOut[]>("/reference/mechanical-test-standards"),
  listProcessReferences: () => request<ProcessReferenceOut[]>("/reference/process-parameters"),
  listLayerStructureReferences: () => request<LayerStructureReferenceOut[]>("/reference/layer-structures"),
  listRecyclabilityCriteria: () => request<RecyclabilityCriterionOut[]>("/reference/recyclability-criteria"),
  listCostReferenceFactors: () => request<CostReferenceFactorOut[]>("/reference/cost-benchmarks"),
  listBenchmarkReferences: () => request<BenchmarkReferenceOut[]>("/reference/benchmarks"),
};
