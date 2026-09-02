"""Kısıt motorunun ORM'den bağımsız, saf/test edilebilir veri tipleri.
Servis katmanı ORM nesnelerini bu dataclass'lara çevirir; motor kendisi hiç
DB görmez — bu da onu deterministik ve birim testi kolay tutar."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MaterialSpec:
    id: str
    name: str
    polymer_code: str
    material_type: str  # virgin | pcr | regranul
    food_contact_eligible: bool
    max_recommended_ratio_pct: float
    degradation_factor: float
    mfi_g_10min: float | None
    cost_per_kg: float
    carbon_factor_kg_co2_per_kg: float
    # Karbon EF veri kalitesi (bkz. app/services/carbon.py). Varsayılan
    # "tanimlanmadi" -- bu alanları hiç geçirmeyen (ör. eski test) çağıranlar
    # dürüstçe 'kaynağı bilinmiyor' durumuna düşer, asla sessizce 'kaynaklı
    # EF' iddia edilmez.
    carbon_ef_status: str = "tanimlanmadi"
    carbon_ef_source: str | None = None
    # Faz G.5 — "Veri Kaynağı" etiketlemesi ve "Karar Dayanağı" için: bu
    # malzemenin bağlı olduğu karbon EF satırının versiyonu (varsa) ve
    # tedarikçi teknik veri föyü referansı (varsa). İkisi de None ise o
    # bilgi kaynağı bu malzeme için TANIMLANMADI demektir, uydurulmaz.
    carbon_ef_version: str | None = None
    technical_datasheet_ref: str | None = None


@dataclass(frozen=True)
class AdditiveSpec:
    id: str
    name: str
    dosage_min_pct: float
    dosage_max_pct: float
    food_contact_eligible: bool


@dataclass(frozen=True)
class LayerCandidate:
    layer_index: int  # 0 = en dış katman, en yüksek index = ürünle/gıdayla temas eden iç katman
    layer_label: str
    material: MaterialSpec
    ratio_pct: float  # bu malzemenin o katman içindeki oranı (0-100)
    thickness_micron: float


@dataclass(frozen=True)
class AdditiveUsage:
    additive: AdditiveSpec
    dosage_pct: float


@dataclass(frozen=True)
class RecipeCandidate:
    layers: list[LayerCandidate]
    additives: list[AdditiveUsage] = field(default_factory=list)

    @property
    def total_micron(self) -> float:
        """Katman kalınlığı, aynı layer_index'i paylaşan birden fazla
        malzeme satırında (karışım/blend) tekrar sayılmaz."""
        by_index: dict[int, float] = {}
        for l in self.layers:
            by_index[l.layer_index] = l.thickness_micron
        return sum(by_index.values())

    @property
    def contact_layers(self) -> list[LayerCandidate]:
        """Ürün/gıda ile temas eden en iç katmanı oluşturan tüm malzeme
        satırları (blend ise birden fazla olabilir)."""
        if not self.layers:
            return []
        max_index = max(l.layer_index for l in self.layers)
        return [l for l in self.layers if l.layer_index == max_index]

    def weighted_composition_pct(self) -> dict[str, float]:
        """Katman kalınlığına göre ağırlıklandırılmış virgin/pcr/regranül
        toplam kompozisyon yüzdesi (tüm reçete geneli)."""
        total = self.total_micron or 1.0
        acc: dict[str, float] = {"virgin": 0.0, "pcr": 0.0, "regranul": 0.0}
        for layer in self.layers:
            weight = layer.thickness_micron / total
            acc[layer.material.material_type] = acc.get(
                layer.material.material_type, 0.0
            ) + weight * (layer.ratio_pct / 100.0) * 100.0
        return acc


@dataclass(frozen=True)
class LineSpec:
    id: str
    name: str
    layer_structure: str
    layer_count: int
    min_micron: float
    max_micron: float
    min_gsm: float | None
    max_gsm: float | None
    supported_packaging_types: list[str]
    material_max_ratio: dict[str, float]  # material_id -> bu hatta izinli azami oran


@dataclass(frozen=True)
class RegulationSpec:
    code: str
    title: str
    category: str
    criteria: dict
    applicable_packaging_types: list[str]


@dataclass(frozen=True)
class PackagingContext:
    packaging_type: str
    food_contact: bool
    target_volume_units: int


@dataclass(frozen=True)
class FailedRecipeSignature:
    """Faz Q.2 (Madde 25) — geçmişte fiziksel testi BAŞARISIZ olmuş
    (`Recipe.status == "revizyon_gerekli"`), AYNI hatta denenmiş bir
    reçetenin GERÇEK kompozisyon imzası + başarısızlık nedeni. `material_ids`
    bir küme (set) olarak karşılaştırılır -- katman sırası/index'i değil,
    HANGİ malzemelerin kullanıldığı önemlidir."""

    recipe_id: str
    version: int
    material_ids: frozenset[str]
    total_micron: float
    basarisizlik_nedeni: str


@dataclass(frozen=True)
class EvaluationContext:
    packaging: PackagingContext
    line: LineSpec
    regulations: list[RegulationSpec]
    # Faz Q.2 (Madde 25) — additive, varsayılan boş liste. Mevcut hiçbir
    # kural bu alanı okumaz/etkilenmez -- geriye dönük tam uyumlu.
    failed_recipe_signatures: list[FailedRecipeSignature] = field(default_factory=list)


# --- Sonuç tipi -------------------------------------------------------

class EvaluationTier:
    KESIN_TEKNIK_KISIT = "kesin_teknik_kisit"
    MALZEME_PROSES_KISITI = "malzeme_proses_kisiti"
    TAHMINI_FIZIKSEL_PERFORMANS = "tahmini_fiziksel_performans"


class EvaluationVerdict:
    ELENDI = "elendi"
    GECTI = "gecti"


class DataConfidence:
    YUKSEK = "yuksek"
    ORTA = "orta"
    DUSUK = "dusuk"


@dataclass(frozen=True)
class EvaluationResult:
    tier: str
    verdict: str
    reason_code: str
    reason_text: str
    data_confidence: str | None = None
