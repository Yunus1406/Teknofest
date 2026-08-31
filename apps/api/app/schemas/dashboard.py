from pydantic import BaseModel


class DashboardSummaryOut(BaseModel):
    """Aşama 1 — Ana Ekran: firmanın genel sürdürülebilirlik durumu.

    Kg değerleri yalnızca gerçekten üretime alınmış (ProductionOrder'ı olan)
    reçetelerin gerçek kütlesinden (alan×kalınlık×yoğunluk) hesaplanır — bu
    yüzden virgin_pct+pcr_pct+regranule_pct her zaman %100'e tamamlanır.
    prevented_waste_kg / carbon_reduction_kg_co2, doğrulanmış bir referans
    reçete bulunamadığında None döner (asla uydurma bir sayı değil)."""

    active_cases: int
    completed_cases: int
    verified_recipes: int
    total_virgin_kg: float
    total_pcr_kg: float
    total_regranule_kg: float
    total_virgin_pct: float
    total_pcr_pct: float
    total_regranule_pct: float
    realized_waste_kg: float
    prevented_waste_kg: float | None
    carbon_reduction_kg_co2: float | None
    # bkz. app/services/carbon.py -- "tanimli_gercek"/"tanimli_demo"/"tanimlanmadi".
    carbon_data_quality: str
    regulatory_alerts: int

    # --- Faz E.5: firma bazlı üst bilgi + ek kazanım metrikleri ----------
    # Company hiç oluşturulmadıysa None -- uydurma bir isim gösterilmez.
    company_name: str | None = None
    facility_name: str | None = None
    active_line_count: int = 0
    registered_material_count: int = 0
    registered_sku_count: int = 0
    # prevented_waste_kg/carbon_reduction_kg_co2 ile AYNI disiplin: referans
    # yoksa None.
    prevented_virgin_kg: float | None = None
    energy_savings_kwh: float | None = None
    active_optimizations: int = 0


class LayerMaterialRowOut(BaseModel):
    """Bir katmanın İÇİNDEKİ tek bir malzeme satırı — ör. 'Katman B: PCR %30'."""

    material_id: str
    material_name: str
    material_type: str  # virgin | pcr | regranul (=PIR)
    ratio_pct: float  # bu malzemenin KATMAN İÇİNDEKİ oranı (0-100)


class LayerCompositionOut(BaseModel):
    """Faz B.3 — 'PCR hangi katmanda?' sorusuna Dashboard 8'de de yanıt
    verebilmek için katman bazlı kırılım (Dashboard 5/7 zaten RecipeOut.layers
    üzerinden bunu taşıyordu; Dashboard 8'in ComparisonOut'u bu fazdan önce
    yalnızca 3 bantlı TOPLAM yüzde taşıyordu)."""

    layer_index: int
    layer_label: str
    thickness_micron: float
    materials: list[LayerMaterialRowOut]


class CompositionSide(BaseModel):
    label: str  # "Mevcut / Referans" | "Önerilen"
    virgin_pct: float
    pcr_pct: float
    regranule_pct: float
    total_micron: float
    cost_per_kg: float
    carbon_kg_co2_per_kg: float
    carbon_data_quality: str
    is_estimated: bool
    layers: list[LayerCompositionOut] = []


class ComparisonOut(BaseModel):
    """Aşama 8 — Mevcut ↔ Önerilen karşılaştırması."""

    reference: CompositionSide | None
    recommended: CompositionSide
    # Referans yoksa None — asla uydurma bir azaltım yüzdesi değil.
    gains: dict[str, float] | None  # {"karbon_azaltimi_pct":.., "maliyet_azaltimi_pct":..}


class FinalResultOut(BaseModel):
    """Aşama 12 — Nihai sonuç (Gerçekleşen)."""

    recipe_id: str
    per_1000_units: dict
    physical_tests_passed: bool
    version_history: list[dict]
