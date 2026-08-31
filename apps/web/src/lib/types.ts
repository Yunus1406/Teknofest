// Backend (apps/api) Pydantic şemalarının TypeScript karşılıkları.
// Kaynak: apps/api/app/schemas/*.py

export interface PackagingRequestCreate {
  packaging_type: string;
  usage_area: string;
  product: string;
  target_market: string;
  food_contact: boolean;
  target_volume_units: number;
  dimensions: Record<string, number | null>;
  // Faz B.5 — bu case var olan bir Ürün/SKU'yu mu hedefliyor? Şu an UI'da bir
  // SKU seçici yok (backend kapasitesi hazır), bu yüzden opsiyonel/undefined kalır.
  sku_id?: string | null;
}

export interface PackagingRequestOut extends PackagingRequestCreate {
  id: string;
  spec_file_name: string | null;
  extracted_fields: Record<string, unknown>;
  status: string;
  sku_id: string | null;
}

export interface ProductSkuOut {
  id: string;
  sku_code: string;
  product_name: string;
  packaging_type: string;
  usage_area: string;
  customer: string | null;
  target_market: string;
  food_contact: boolean;
  dimensions: Record<string, number | null>;
  film_thickness_micron: number | null;
  gsm: number | null;
  layer_count: number | null;
  layer_structure: string | null;
  line_id: string | null;
  current_recipe_id: string | null;
  technical_spec_ref: string | null;
  physical_test_criteria: Record<string, unknown>;
}

export interface SpecExtractionOut {
  packaging_type: string | null;
  usage_area: string | null;
  product: string | null;
  target_market: string | null;
  food_contact: boolean | null;
  target_volume_units: number | null;
  dimensions: Record<string, number | null>;
  field_confidence: Record<string, "yuksek" | "orta" | "dusuk">;
}

export interface RegulatoryAssessmentOut {
  id: string;
  regulation_id: string;
  verdict: "uygun_gorunuyor" | "inceleme_gerekli" | "uygun_degil";
  reasoning: string;
}

export interface RegulatoryAssessmentSummaryOut {
  overall_verdict: "uygun_gorunuyor" | "inceleme_gerekli" | "uygun_degil";
  assessments: RegulatoryAssessmentOut[];
}

export interface RegulationOut {
  id: string;
  code: string;
  title: string;
  category: string;
  description: string;
  criteria: Record<string, unknown>;
  applicable_packaging_types: string[];
}

export interface ProductionLineOut {
  id: string;
  name: string;
  layer_structure: string;
  layer_count: number;
  min_micron: number;
  max_micron: number;
  min_gsm: number | null;
  max_gsm: number | null;
  line_speed_m_min: number;
  supported_packaging_types: string[];
  energy_kwh_per_kg: number;
  active: boolean;
}

export interface LineMatchOut {
  line: ProductionLineOut;
  compatible_material_ids: string[];
  match_reason: string;
}

export interface MaterialOut {
  id: string;
  polymer_id: string;
  name: string;
  material_type: "virgin" | "pcr" | "regranul";
  source: string | null;
  manufacturer: string | null;
  supplier: string | null;
  color: string | null;
  certification_status: string | null;
  suitable_layer_position: string | null;
  mfi_g_10min: number | null;
  density_g_cm3: number | null;
  degradation_factor: number;
  tensile_strength_mpa: number | null;
  elongation_pct: number | null;
  dart_impact_g: number | null;
  melt_temp_c: number | null;
  processing_temp_c: number | null;
  additive_content_note: string | null;
  food_contact_eligible: boolean;
  max_recommended_ratio_pct: number;
  cost_per_kg: number;
  carbon_factor_kg_co2_per_kg: number;
  carbon_ef_id: string | null;
  stock_qty_kg: number | null;
  lot_number: string | null;
  // PCR'a özgü
  contamination_level: string | null;
  odor_level: string | null;
  technical_constraints: string | null;
  // PIR/Regranül'e özgü (izlenebilirlik)
  source_process: string | null;
  production_date: string | null;
  source_machine_id: string | null;
  source_recipe_id: string | null;
}

export interface CarbonEmissionFactorOut {
  id: string;
  material_key: string;
  ef_value: number;
  unit: string;
  source: string;
  year: number | null;
  geography: string | null;
  version: string | null;
  is_demo_placeholder: boolean;
}

export interface RecipeLayerOut {
  layer_index: number;
  layer_label: string;
  material_id: string;
  ratio_pct: number;
  thickness_micron: number;
}

export interface RecipeEvaluationOut {
  tier: "kesin_teknik_kisit" | "malzeme_proses_kisiti" | "tahmini_fiziksel_performans";
  verdict: "elendi" | "gecti";
  reason_code: string;
  reason_text: string;
  data_confidence: "yuksek" | "orta" | "dusuk" | null;
}

export interface RecipeMetricOut {
  metric_type: string;
  value: number;
  unit: string;
  is_estimated: boolean;
  data_source_type: string;
}

export interface RecipeOut {
  id: string;
  packaging_request_id: string;
  version: number;
  parent_recipe_id: string | null;
  line_id: string | null;
  source: "referans_receteden" | "sistem_uretti";
  status: string;
  is_verified: boolean;
  total_gsm: number | null;
  total_micron: number | null;
  layers: RecipeLayerOut[];
  additives: { additive_id: string; dosage_pct: number }[];
  evaluations: RecipeEvaluationOut[];
  metrics: RecipeMetricOut[];
}

export interface OptimizationCandidateOut {
  id: string;
  recipe_id: string;
  score: number;
  rank: number;
  is_finalist: boolean;
  score_breakdown: Record<string, number>;
  carbon_data_quality: string;
  justification_text: string | null;
  decision_basis: {
    gecmis_receteler: string[];
    mevzuat_maddeleri: string[];
    hat_parametreleri: Record<string, string>;
  };
  recipe: RecipeOut;
}

export interface EliminatedCandidateOut {
  composition_summary: string;
  reasons: string[];
  summary_text: string;
}

export interface OptimizationRunOut {
  id: string;
  packaging_request_id: string;
  finalists: OptimizationCandidateOut[];
  notable_eliminated: EliminatedCandidateOut[];
  generated_candidate_count: number;
  survived_constraint_engine_count: number;
}

export interface LayerMaterialRowOut {
  material_id: string;
  material_name: string;
  material_type: "virgin" | "pcr" | "regranul";
  ratio_pct: number;
}

export interface LayerCompositionOut {
  layer_index: number;
  layer_label: string;
  thickness_micron: number;
  materials: LayerMaterialRowOut[];
}

export interface CompositionSide {
  label: string;
  virgin_pct: number;
  pcr_pct: number;
  regranule_pct: number;
  total_micron: number;
  cost_per_kg: number;
  carbon_kg_co2_per_kg: number;
  carbon_data_quality: string;
  is_estimated: boolean;
  layers: LayerCompositionOut[];
}

export interface ComparisonOut {
  reference: CompositionSide | null;
  recommended: CompositionSide;
  gains: Record<string, number> | null;
}

export interface ProductionOrderOut {
  id: string;
  recipe_id: string;
  line_id: string;
  status: string;
  scheduled_qty_units: number;
}

export interface ProductionLiveDataOut {
  ts: string | null;
  produced_qty_units: number; // kümülatif
  period_produced_qty_units: number; // dönemsel
  material_consumption: Record<string, number>;
  line_speed_m_min: number;
  energy_kwh: number; // dönemsel
  cumulative_energy_kwh: number;
  waste_kg: number; // dönemsel
  cumulative_waste_kg: number;
  source: string;
}

export interface PhysicalTestIn {
  test_type: string;
  value: number;
  unit: string;
  target_min: number | null;
  target_max: number | null;
  test_method: string | null;
}

export interface SuggestedTestTargetOut {
  test_type: string;
  unit: string;
  test_method: string;
  nominal_value: number | null;
  target_min: number | null;
  target_max: number | null;
  note: string;
}

export interface PhysicalVerificationResultOut {
  all_passed: boolean;
  new_recipe_version: RecipeOut | null;
}

export interface FinalResultOut {
  recipe_id: string;
  // karbon_veri_kalitesi ve _uyari gibi metin alanları da taşıyabilir.
  per_1000_units: Record<string, number | string | null>;
  physical_tests_passed: boolean;
  version_history: {
    id: string;
    version: number;
    status: string;
    is_verified: boolean;
    created_at: string;
  }[];
}

export interface DashboardSummaryOut {
  active_cases: number;
  completed_cases: number;
  verified_recipes: number;
  total_virgin_kg: number;
  total_pcr_kg: number;
  total_regranule_kg: number;
  total_virgin_pct: number;
  total_pcr_pct: number;
  total_regranule_pct: number;
  realized_waste_kg: number;
  // Doğrulanmış bir referans reçete yoksa null — "0 kazanım" ile
  // "karşılaştırma temeli yok" farklıdır, UI bunu ayrı göstermeli.
  prevented_waste_kg: number | null;
  carbon_reduction_kg_co2: number | null;
  carbon_data_quality: string;
  regulatory_alerts: number;
}

// Faz B.9 — Firma Hafızası Zinciri (bkz. apps/api/app/schemas/traceability.py).
// Faz C.2'de Dijital Ürün Pasaportu'nun Yetkili Alan'ında yeniden kullanılıyor.
export interface TraceabilityCompanyOut {
  id: string;
  name: string;
}

export interface TraceabilityFacilityOut {
  id: string;
  name: string;
  address: string | null;
}

export interface TraceabilityMachineOut {
  id: string;
  name: string;
  process_type: string | null;
}

export interface TraceabilitySkuOut {
  id: string;
  sku_code: string;
  product_name: string;
}

export interface TraceabilityPackagingRequestOut {
  id: string;
  packaging_type: string;
  product: string;
}

export interface TraceabilityRecipeOut {
  id: string;
  version: number;
  status: string;
  is_verified: boolean;
  total_micron: number | null;
  total_gsm: number | null;
}

export interface TraceabilityMaterialOut {
  id: string;
  name: string;
  material_type: string;
}

export interface TraceabilityCarbonEfOut {
  id: string;
  ef_value: number;
  unit: string;
  is_demo_placeholder: boolean;
  source: string;
}

export interface TraceabilityLayerOut {
  layer_index: number;
  layer_label: string;
  ratio_pct: number;
  thickness_micron: number;
  material: TraceabilityMaterialOut | null;
  carbon_ef: TraceabilityCarbonEfOut | null;
}

export interface TraceabilityWasteRecordOut {
  waste_type: string;
  kg: number;
  recoverable: boolean;
}

export interface TraceabilityProductionOrderOut {
  id: string;
  status: string;
  scheduled_qty_units: number;
  operator: string | null;
  waste_records: TraceabilityWasteRecordOut[];
}

export interface TraceabilityPhysicalTestOut {
  test_type: string;
  value: number;
  unit: string;
  passed: boolean;
}

export interface TraceabilityRegulatoryAssessmentOut {
  regulation_code: string | null;
  verdict: string;
  reasoning: string;
}

export interface RecipeTraceabilityOut {
  recipe_id: string;
  company: TraceabilityCompanyOut | null;
  facility: TraceabilityFacilityOut | null;
  machine: TraceabilityMachineOut | null;
  sku: TraceabilitySkuOut | null;
  packaging_request: TraceabilityPackagingRequestOut | null;
  recipe: TraceabilityRecipeOut;
  layers: TraceabilityLayerOut[];
  production_orders: TraceabilityProductionOrderOut[];
  physical_tests: TraceabilityPhysicalTestOut[];
  regulatory_assessments: TraceabilityRegulatoryAssessmentOut[];
}

// Faz C.2 — Dijital Ürün Pasaportu (bkz. apps/api/app/schemas/passport.py).
// `public` her zaman dolu; `authorized` sadece doğru `dpp_authorized_key`
// ile istendiğinde dolar, aksi halde `null` (sessizce — sızıntı yok).
export interface PassportHeaderOut {
  passport_no: string;
  revision: number;
  sku_code: string | null;
  product_name: string | null;
  recipe_id: string;
  recipe_version: number;
  facility_name: string | null;
  company_name: string | null;
  production_date: string | null;
  line_name: string | null;
  packaging_type: string | null;
  target_market: string | null;
}

export interface PassportStatusSummaryOut {
  digital_identity: string;
  recipe_status: string;
  physical_performance: string;
  data_traceability: string;
  ppwr_status: string;
  last_updated: string;
}

export interface PassportMaterialSummaryOut {
  total_gsm: number | null;
  total_micron: number | null;
  layer_count: number;
  layer_structure: string | null;
  polymers: string[];
  virgin_pct: number;
  pcr_pct: number;
  regranule_pct: number;
}

export interface PassportEnvironmentalOut {
  per_1000_units: Record<string, number | string | null> | null;
  gains_pct: Record<string, number> | null;
  has_reference: boolean;
}

export interface PassportPhysicalTestOut {
  test_type: string;
  value: number;
  unit: string;
  target_min: number | null;
  target_max: number | null;
  test_method: string | null;
  passed: boolean;
}

export interface PassportRegulatoryItemOut {
  regulation_code: string | null;
  article: string | null;
  verdict: string;
}

export interface PassportVersionOut {
  id: string;
  version: number;
  status: string;
  is_verified: boolean;
  created_at: string;
}

export interface PassportPublicOut {
  header: PassportHeaderOut;
  status_summary: PassportStatusSummaryOut;
  material_summary: PassportMaterialSummaryOut;
  environmental: PassportEnvironmentalOut;
  physical_tests: PassportPhysicalTestOut[];
  regulatory: PassportRegulatoryItemOut[];
  regulatory_disclaimer: string;
  version_history: PassportVersionOut[];
}

export interface PassportLayerMaterialDetailOut {
  layer_index: number;
  layer_label: string;
  material_name: string | null;
  material_type: string | null;
  manufacturer: string | null;
  supplier: string | null;
  lot_number: string | null;
  certification_status: string | null;
  ratio_pct: number;
}

export interface PassportRegulatoryReasoningOut {
  regulation_code: string | null;
  reasoning: string;
}

export interface PassportAuthorizedOut {
  layer_materials: PassportLayerMaterialDetailOut[];
  traceability: RecipeTraceabilityOut;
  regulatory_reasoning: PassportRegulatoryReasoningOut[];
}

export interface DigitalProductPassportOut {
  public: PassportPublicOut;
  authorized: PassportAuthorizedOut | null;
  qr_code_data_uri: string;
}
