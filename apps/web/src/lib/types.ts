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
  // Faz G.1 — Aşama 2'nin "Çıkarılan Bilgileri Kontrol Edin" ekranının
  // gösterdiği ek alanlar (hepsi opsiyonel, uydurma değer yok).
  target_thickness_micron?: number | null;
  target_gsm?: number | null;
  physical_performance_notes?: string | null;
}

export interface PackagingRequestOut extends PackagingRequestCreate {
  id: string;
  spec_file_name: string | null;
  extracted_fields: Record<string, unknown>;
  status: string;
  sku_id: string | null;
  target_thickness_micron: number | null;
  target_gsm: number | null;
  physical_performance_notes: string | null;
}

export interface ProductSkuOut {
  id: string;
  sku_code: string;
  product_name: string;
  packaging_type: string;
  usage_area: string;
  customer: string | null;
  customer_sector: string | null;
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

export interface ProductSkuCreate {
  sku_code: string;
  product_name: string;
  packaging_type: string;
  usage_area: string;
  customer?: string | null;
  customer_sector?: string | null;
  target_market: string;
  food_contact?: boolean;
  dimensions?: Record<string, number | null>;
  film_thickness_micron?: number | null;
  gsm?: number | null;
  layer_count?: number | null;
  layer_structure?: string | null;
  line_id?: string | null;
  technical_spec_ref?: string | null;
  physical_test_criteria?: Record<string, unknown>;
}

export type ProductSkuUpdate = Partial<ProductSkuCreate>;

export interface ProductSkuDetailOut extends ProductSkuOut {
  traceability: RecipeTraceabilityOut | null;
}

export interface SpecExtractionOut {
  packaging_type: string | null;
  usage_area: string | null;
  product: string | null;
  target_market: string | null;
  food_contact: boolean | null;
  target_volume_units: number | null;
  dimensions: Record<string, number | null>;
  target_thickness_micron: number | null;
  target_gsm: number | null;
  physical_performance_notes: string | null;
  field_confidence: Record<string, "yuksek" | "orta" | "dusuk">;
}

export interface RecyclabilityDimensionOut {
  dimension: string;
  criterion_text: string;
  weight_pct: number | null;
  packaging_category: string | null;
}

// Faz G.2 — eskiden 3 durumdu; veri_eksik/henuz_metodoloji_yok bir onay/red
// İDDİASI taşımaz, bkz. app/models/enums.py RegulatoryVerdict.
export type RegulatoryVerdictValue =
  | "uygun_gorunuyor"
  | "inceleme_gerekli"
  | "uygun_degil"
  | "veri_eksik"
  | "henuz_metodoloji_yok";

export interface RegulatoryAssessmentOut {
  id: string;
  regulation_id: string;
  verdict: RegulatoryVerdictValue;
  reasoning: string;
  // Faz F.9 — SADECE PPWR Md.6 (geri dönüştürülebilirlik) değerlendirmesinde
  // dolu, diğer maddelerde null.
  recyclability_breakdown: { dimensions: RecyclabilityDimensionOut[] } | null;
}

export interface RegulatoryAssessmentSummaryOut {
  overall_verdict: RegulatoryVerdictValue;
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
  facility_id: string | null;
  name: string;
  process_type: string | null;
  layer_structure: string;
  layer_count: number;
  extruder_count: number | null;
  min_micron: number;
  max_micron: number;
  min_gsm: number | null;
  max_gsm: number | null;
  max_width_mm: number | null;
  min_dosage_pct: number | null;
  max_dosage_pct: number | null;
  line_speed_m_min: number;
  supported_packaging_types: string[];
  energy_kwh_per_kg: number;
  active: boolean;
  plc_enabled: boolean;
  opc_ua_enabled: boolean;
  modbus_tcp_enabled: boolean;
  api_enabled: boolean;
  // Faz E.2 — Makine Parkı teknik kartı (hepsi opsiyonel).
  manufacturer: string | null;
  model: string | null;
  install_year: number | null;
  nominal_capacity_kg_year: number | null;
  actual_capacity_kg_year: number | null;
  min_line_speed_m_min: number | null;
  max_line_speed_m_min: number | null;
  layer_structure_type: string | null;
  screw_diameter_mm: number | null;
  ld_ratio: number | null;
  suitable_polymer_codes: string[];
  pcr_capable: boolean | null;
  pir_capable: boolean | null;
  max_pcr_technical_pct: number | null;
  max_pir_technical_pct: number | null;
  gravimetric_dosing_equipped: boolean | null;
  online_thickness_control: boolean | null;
  energy_metering_equipped: boolean | null;
  average_waste_rate_pct: number | null;
  availability_status: string | null;
  // Faz G.3 — "Kayıtlı Makineden Hat Oluştur" ile birden fazla kayıtlı
  // satırın birleşimi olarak mı tanımlandı? null/[] = hayır.
  component_line_ids: string[] | null;
}

export interface ProductionLineCreate {
  facility_id?: string | null;
  name: string;
  process_type?: string | null;
  layer_structure: string;
  layer_count?: number;
  extruder_count?: number | null;
  min_micron: number;
  max_micron: number;
  min_gsm?: number | null;
  max_gsm?: number | null;
  max_width_mm?: number | null;
  min_dosage_pct?: number | null;
  max_dosage_pct?: number | null;
  line_speed_m_min?: number;
  supported_packaging_types?: string[];
  energy_kwh_per_kg?: number;
  active?: boolean;
  manufacturer?: string | null;
  model?: string | null;
  install_year?: number | null;
  nominal_capacity_kg_year?: number | null;
  actual_capacity_kg_year?: number | null;
  min_line_speed_m_min?: number | null;
  max_line_speed_m_min?: number | null;
  layer_structure_type?: string | null;
  screw_diameter_mm?: number | null;
  ld_ratio?: number | null;
  suitable_polymer_codes?: string[];
  pcr_capable?: boolean | null;
  pir_capable?: boolean | null;
  max_pcr_technical_pct?: number | null;
  max_pir_technical_pct?: number | null;
  gravimetric_dosing_equipped?: boolean | null;
  online_thickness_control?: boolean | null;
  energy_metering_equipped?: boolean | null;
  average_waste_rate_pct?: number | null;
  availability_status?: string | null;
  component_line_ids?: string[] | null;
}

export type ProductionLineUpdate = Partial<ProductionLineCreate>;

// Faz K.4 — Aşama 4'ün uygunluk matrisindeki 5 kriter.
export interface LineMatchCriteriaOut {
  proses: boolean;
  malzeme_uyumu: boolean;
  mikron_araligi: boolean;
  katman_yapisi: boolean;
  ambalaj_turu: boolean;
}

export interface LineMatchOut {
  line: ProductionLineOut;
  compatible_material_ids: string[];
  match_reason: string;
  eligible: boolean;
  score_pct: number;
  criteria: LineMatchCriteriaOut | null;
  missing: string[];
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
  // Faz E.3 — genişletilmiş teknik kart
  currency: string;
  origin_country: string | null;
  technical_datasheet_ref: string | null;
  compliance_documents_ref: string | null;
  // PCR'a özgü
  contamination_level: string | null;
  odor_level: string | null;
  technical_constraints: string | null;
  post_consumer_content_pct: number | null;
  // PIR/Regranül'e özgü (izlenebilirlik)
  source_process: string | null;
  production_date: string | null;
  source_machine_id: string | null;
  source_recipe_id: string | null;
}

export interface MaterialCreate {
  polymer_id: string;
  name: string;
  material_type: "virgin" | "pcr" | "regranul";
  source?: string | null;
  manufacturer?: string | null;
  supplier?: string | null;
  color?: string | null;
  certification_status?: string | null;
  suitable_layer_position?: string | null;
  mfi_g_10min?: number | null;
  density_g_cm3?: number | null;
  degradation_factor?: number;
  tensile_strength_mpa?: number | null;
  elongation_pct?: number | null;
  dart_impact_g?: number | null;
  melt_temp_c?: number | null;
  processing_temp_c?: number | null;
  additive_content_note?: string | null;
  food_contact_eligible?: boolean;
  max_recommended_ratio_pct?: number;
  cost_per_kg?: number;
  carbon_factor_kg_co2_per_kg?: number;
  carbon_ef_id?: string | null;
  stock_qty_kg?: number | null;
  lot_number?: string | null;
  currency?: string;
  origin_country?: string | null;
  technical_datasheet_ref?: string | null;
  compliance_documents_ref?: string | null;
  contamination_level?: string | null;
  odor_level?: string | null;
  technical_constraints?: string | null;
  post_consumer_content_pct?: number | null;
  source_process?: string | null;
  production_date?: string | null;
  source_machine_id?: string | null;
  source_recipe_id?: string | null;
}

export type MaterialUpdate = Partial<Omit<MaterialCreate, "material_type">>;

export interface PolymerOut {
  id: string;
  code: string;
  name: string;
  category: string;
  base_properties: Record<string, unknown>;
}

export interface AdditiveOut {
  id: string;
  name: string;
  additive_type: string;
  manufacturer: string | null;
  carrier_polymer: string | null;
  regulatory_document_ref: string | null;
  effects: Record<string, unknown>;
  dosage_min_pct: number;
  dosage_max_pct: number;
  food_contact_eligible: boolean;
  cost_per_kg: number;
  carbon_ef_id: string | null;
}

export interface AdditiveCreate {
  name: string;
  additive_type: string;
  manufacturer?: string | null;
  carrier_polymer?: string | null;
  regulatory_document_ref?: string | null;
  effects?: Record<string, unknown>;
  dosage_min_pct?: number;
  dosage_max_pct?: number;
  food_contact_eligible?: boolean;
  cost_per_kg?: number;
  carbon_ef_id?: string | null;
}

export type AdditiveUpdate = Partial<AdditiveCreate>;

export interface CarbonEmissionFactorOut {
  id: string;
  material_key: string;
  factor_type: string;
  ef_value: number;
  unit: string;
  source: string;
  year: number | null;
  geography: string | null;
  version: string | null;
  is_demo_placeholder: boolean;
}

// --- Faz F — Ambalaj Referans Veri Kütüphanesi (app/schemas/reference_library.py) ---

export interface RegulationRequirementOut {
  id: string;
  regulation_id: string;
  regulation_no: string;
  article: string;
  sub_article: string | null;
  packaging_category: string | null;
  target_year: number | null;
  requirement_text: string;
  pcr_only: boolean;
  exception_text: string | null;
  effective_date: string | null;
  version: string;
  source: string | null;
  default_verdict: string;
  threshold_value: number | null;
  threshold_unit: string | null;
  last_reviewed_at: string | null;
}

export interface ChemicalRestrictionOut {
  id: string;
  substance_group: string;
  restriction_type: string;
  limit_value: number;
  limit_unit: string;
  food_contact_only: boolean;
  regulation_id: string | null;
  source: string | null;
  year: number | null;
  version: string;
  is_demo_placeholder: boolean;
}

export interface FoodContactRequirementOut {
  id: string;
  regulation_id: string;
  requirement_type: string;
  substance: string | null;
  limit_value: number | null;
  limit_unit: string | null;
  applies_to_pcr: boolean;
  notes: string | null;
  source: string | null;
  year: number | null;
  version: string;
  is_demo_placeholder: boolean;
}

export interface PolymerTechnicalReferenceOut {
  id: string;
  polymer_id: string;
  property_name: string;
  typical_min: number | null;
  typical_max: number | null;
  unit: string;
  source: string | null;
  year: number | null;
  version: string;
  is_demo_placeholder: boolean;
}

export interface ProcessReferenceOut {
  id: string;
  process_type: string;
  parameter_name: string;
  typical_min: number | null;
  typical_max: number | null;
  unit: string;
  source: string | null;
  year: number | null;
  version: string;
  is_demo_placeholder: boolean;
}

export interface LayerStructureReferenceOut {
  id: string;
  structure_pattern: string;
  typical_usage: string;
  barrier_properties: string;
  source: string | null;
  year: number | null;
  version: string;
  is_demo_placeholder: boolean;
}

export interface MechanicalTestStandardOut {
  id: string;
  test_type: string;
  standard_name: string;
  unit: string;
  packaging_category: string | null;
  typical_min: number | null;
  typical_max: number | null;
  source: string | null;
  year: number | null;
  version: string;
  is_demo_placeholder: boolean;
}

export interface RecyclabilityCriterionOut {
  id: string;
  packaging_category: string | null;
  dimension: string;
  criterion_text: string;
  weight_pct: number | null;
  source: string | null;
  year: number | null;
  version: string;
  is_demo_placeholder: boolean;
}

export interface CostReferenceFactorOut {
  id: string;
  cost_type: string;
  typical_min: number | null;
  typical_max: number | null;
  unit: string;
  currency: string;
  source: string | null;
  year: number | null;
  geography: string | null;
  version: string;
  is_demo_placeholder: boolean;
}

export interface BenchmarkReferenceOut {
  id: string;
  packaging_category: string | null;
  metric_name: string;
  typical_value: number | null;
  unit: string;
  source: string | null;
  year: number | null;
  version: string;
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
  // Faz G.4 — firma hafızası taramasının kanıtı: {tier, evidence_count,
  // candidate_recipe_ids}. Referans bulunamadıysa (virgin-only üretim) null.
  reference_search_evidence: {
    tier: string;
    evidence_count: number;
    candidate_recipe_ids: string[];
  } | null;
  // Faz G.5 — bu reçetenin GERÇEKTEN beslendiği veri kaynakları (birden
  // fazla olabilir). Sabit 8 değerli kelime dağarcığı — mevcut tek-değerli
  // `data_source_type` (RecipeMetricOut) ile KARIŞTIRILMAZ, ayrı amaç.
  data_source_tags: string[] | null;
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
    // Faz G.5 — geçmiş reçeteler bulunduysa hangi kademede (bkz.
    // referenceSearchTierLabel); hiç bulunamadıysa null.
    gecmis_recete_kademe: string | null;
    mevzuat_maddeleri: string[];
    hat_parametreleri: Record<string, string>;
    hammadde_veri_foyu_sayisi: number;
    karbon_ef_versiyonu: string | null;
  };
  recipe: RecipeOut;
}

// Faz J.0 — her gerekçenin GERÇEK EvaluationTier'ı (kesin_teknik_kisit/
// malzeme_proses_kisiti) korunur; Dashboard 6 bunu yapısal olarak
// ayırt edebilsin diye (önceden sadece düz metin taşınıyordu).
export interface EliminationReasonOut {
  tier: string;
  text: string;
}

export interface EliminatedCandidateOut {
  composition_summary: string;
  reasons: EliminationReasonOut[];
  summary_text: string;
}

// Faz D.1 — "Adaylar Nasıl Oluşturuldu?". `total`, backend'in gerçekten
// ürettiği generated_candidate_count ile HER ZAMAN birebir eşittir (aynı
// hesaplamadan türetilir, bkz. app/optimization/candidate_generator.py).
export interface GenerationBreakdownLayerOut {
  layer_label: string;
  virgin_material_name: string;
  recycled_material_names: string[];
  variant_count: number;
}

export interface GenerationBreakdownOut {
  layers: GenerationBreakdownLayerOut[];
  total: number;
  formula_text: string;
}

export interface OptimizationRunOut {
  id: string;
  packaging_request_id: string;
  finalists: OptimizationCandidateOut[];
  notable_eliminated: EliminatedCandidateOut[];
  generated_candidate_count: number;
  survived_constraint_engine_count: number;
  generation_breakdown: GenerationBreakdownOut | null;
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
  // Faz H.1 — 1000 birim başına TAHMİNİ mutlak kütle dengesi (sadece
  // is_estimated=true tarafında dolu; ölçü/hat verisi eksikse null).
  virgin_kg: number | null;
  pcr_kg: number | null;
  regranul_kg: number | null;
  fire_kg: number | null;
  enerji_kwh: number | null;
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
  // Faz H.2 — üretim emrini oluşturma anında dolar.
  order_no: string | null;
  approved_by: string | null;
  approved_at: string | null;
}

export interface OrderAdditiveOut {
  layer_index: number | null;
  additive_id: string;
  additive_name: string;
  dosage_pct: number;
}

export interface ProcessParameterSuggestionOut {
  parameter_name: string;
  typical_min: number | null;
  typical_max: number | null;
  unit: string;
  source: string | null;
}

// Faz H.2 — Aşama 9'un gerçek bir üretim talimatına dönüşmesi. Hat
// eşleşmemişse veya F.7 kütüphanesinde eşleşme yoksa ilgili alanlar
// boş/null kalır (uydurulmaz).
export interface ProductionOrderSummaryOut {
  order_no: string | null;
  recipe_code: string;
  recipe_version: number;
  total_micron: number | null;
  layers: LayerCompositionOut[];
  additives: OrderAdditiveOut[];
  target_line_speed_m_min: number | null;
  target_process_parameters: ProcessParameterSuggestionOut[];
  approved_by: string | null;
  approved_at: string | null;
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
  // Faz F.6 — ayrı, açıkça "öneri" etiketli alan; target_min/target_max DEĞİLDİR.
  suggested_min: number | null;
  suggested_max: number | null;
  suggestion_source: string | null;
}

// Faz D.2 — basarili/basarisiz/beklemede. `passed` sadece geriye dönük
// uyumluluk için tutulur; UI Geçti/Kaldı/Test Edilmedi metnini HER ZAMAN
// `result`tan üretmeli (beklemede'de de `passed` false'dur).
export interface PhysicalTestOut {
  id: string;
  test_type: string;
  value: number;
  unit: string;
  target_min: number | null;
  target_max: number | null;
  test_method: string | null;
  result: string;
  passed: boolean;
  source: string;
}

export interface PhysicalVerificationResultOut {
  all_passed: boolean;
  results: PhysicalTestOut[];
  new_recipe_version: RecipeOut | null;
}

// Faz H.4 — Aşama 12'nin üç sütunlu karşılaştırması. `reference`/`gains`
// referans yoksa null — asla uydurma bir azaltım yüzdesi gösterilmez.
export interface TripleComparisonOut {
  reference: Record<string, number | string | null> | null;
  tahmini: Record<string, number | string | null>;
  gerceklesen: Record<string, number | string | null> | null;
  gains: Record<string, number> | null;
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
  triple_comparison: TripleComparisonOut;
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

  // Faz E.5 — firma bazlı üst bilgi + ek kazanım metrikleri
  company_name: string | null;
  facility_name: string | null;
  active_line_count: number;
  registered_material_count: number;
  registered_sku_count: number;
  // prevented_waste_kg ile AYNI disiplin: referans yoksa null.
  prevented_virgin_kg: number | null;
  energy_savings_kwh: number | null;
  active_optimizations: number;
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
  version: string | null;
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
  result: string; // Faz D.2 — basarili/basarisiz/beklemede
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
  // Faz I.1 — Bölüm D: Referans|Tahmini|Gerçekleşen (H.4'ün TripleComparisonOut'uyla aynı şekil).
  triple_comparison: TripleComparisonOut | null;
}

// Faz I.1 — Bölüm C (Döngüsellik). İkisi de yoksa null (uydurulmaz).
export interface PassportCircularityOut {
  recyclability_breakdown: { dimensions: RecyclabilityDimensionOut[] } | null;
  pcr_trend: { onceki_pcr_pct: number; guncel_pcr_pct: number } | null;
}

export interface PassportPhysicalTestOut {
  test_type: string;
  value: number;
  unit: string;
  target_min: number | null;
  target_max: number | null;
  test_method: string | null;
  result: string; // Faz D.2 — basarili/basarisiz/beklemede
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
  // Faz I.1 — Bölüm C.
  circularity: PassportCircularityOut;
  // Faz I.1 — Bölüm F: ticari bir bilgi değil, public kalır.
  food_contact: boolean | null;
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

// Faz I.1 — Bölüm B: katkı maddesi/masterbatch dozajı, ticari detay olduğu için authorized altında.
export interface PassportAdditiveOut {
  layer_index: number | null;
  additive_name: string | null;
  additive_type: string | null;
  manufacturer: string | null;
  dosage_pct: number;
}

// Faz I.3 — Gerçek Öğrenme Hafızası: V1→V2→V3 zincirinin bir halkası.
export interface CausalChainNodeOut {
  id: string;
  version: number;
  status: string;
  is_verified: boolean;
  created_at: string;
  diff_from_previous: Record<string, unknown>[] | null;
  line_name: string | null;
  target_process_parameters: { parameter_name: string; typical_min: number | null; typical_max: number | null; unit: string }[];
  gerceklesen_fire_kg: number | null;
  gerceklesen_enerji_kwh: number | null;
  physical_test_summary: { basarili: number; basarisiz: number; beklemede: number };
}

export interface PassportAuthorizedOut {
  layer_materials: PassportLayerMaterialDetailOut[];
  additives: PassportAdditiveOut[];
  traceability: RecipeTraceabilityOut;
  regulatory_reasoning: PassportRegulatoryReasoningOut[];
  // Faz I.1 — Bölüm G: Faz G.4'ün firma hafızası tarama kanıtı (varsa).
  reference_search_evidence: {
    tier: string;
    evidence_count: number;
    candidate_recipe_ids: string[];
  } | null;
  // Faz I.3 — Bölüm G: V1→V2→V3 zincirinin nedensel halkaları.
  causal_chain: CausalChainNodeOut[];
}

export interface DigitalProductPassportOut {
  public: PassportPublicOut;
  authorized: PassportAuthorizedOut | null;
  qr_code_data_uri: string;
}

// Faz E.1 — Firma Profili. `bool | null` alanlar `null` = "Veri Girilmedi"
// (asla `false` varsayılmaz, bkz. apps/api/app/models/company.py).
export interface CompanyOut {
  id: string;
  name: string;
  trade_name: string | null;
  tax_country: string | null;
  country: string | null;
  city: string | null;
  website: string | null;
  business_area: string | null;
  nace_code: string | null;
  employee_count: number | null;
  annual_production_capacity_tons: number | null;
  annual_actual_production_tons: number | null;
  main_export_markets: string[];
  exports_to_eu: boolean | null;
  produces_food_packaging: boolean | null;
  logo_url: string | null;
}

export interface CompanyCreate {
  name: string;
  trade_name?: string | null;
  tax_country?: string | null;
  country?: string | null;
  city?: string | null;
  website?: string | null;
  business_area?: string | null;
  nace_code?: string | null;
  employee_count?: number | null;
  annual_production_capacity_tons?: number | null;
  annual_actual_production_tons?: number | null;
  main_export_markets?: string[];
  exports_to_eu?: boolean | null;
  produces_food_packaging?: boolean | null;
  logo_url?: string | null;
}

export type CompanyUpdate = Partial<CompanyCreate>;

export interface FacilityOut {
  id: string;
  company_id: string;
  name: string;
  address: string | null;
  code: string | null;
  production_area_m2: number | null;
  annual_capacity_tons: number | null;
  working_days_per_year: number | null;
  shift_count: number | null;
  working_hours_per_day: number | null;
  main_processes: string[];
  electricity_consumption_kwh_year: number | null;
  gas_consumption_m3_year: number | null;
  renewable_energy_used: boolean | null;
  renewable_energy_pct: number | null;
}

export interface FacilityUpsert {
  name: string;
  address?: string | null;
  code?: string | null;
  production_area_m2?: number | null;
  annual_capacity_tons?: number | null;
  working_days_per_year?: number | null;
  shift_count?: number | null;
  working_hours_per_day?: number | null;
  main_processes?: string[];
  electricity_consumption_kwh_year?: number | null;
  gas_consumption_m3_year?: number | null;
  renewable_energy_used?: boolean | null;
  renewable_energy_pct?: number | null;
}

export interface CompanyProfileOut {
  company: CompanyOut;
  facilities: FacilityOut[];
}
