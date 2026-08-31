"""Aşama 1 (Ana Ekran) için DB'den gerçek kg/adet bazlı agregasyon.

Önceki hatalar:
  - RecipeMetric'te YÜZDE (0-100) olarak saklanan virgin/PCR/regranül
    oranları doğrudan TOPLANIP 'kg' gibi gösteriliyordu — hem birim hatası
    hem de aynı optimizasyon koşusundaki 4 finalist adayın hepsi ayrı ayrı
    toplanıyordu (oysa yalnızca biri gerçekten üretilecek). %2852 gibi
    imkansız sonuçlar buradan geliyordu.
  - 'Önlenen Fire' / 'Karbon Azaltımı' hiçbir doğrulanmış referans reçete
    yokken bile sabit bir taban değerle (`5.0 - fire_kg` gibi) hesaplanıp
    gösteriliyordu — karşılaştırma temeli olmayan bir iddia.

Bu modül: (1) yalnızca gerçekten ÜRETİME ALINMIŞ (ProductionOrder'ı olan)
reçetelerin gerçek kütlesini (mass_balance) toplar — her vaka bir kez
sayılır; (2) 'aktif çalışma' sayısını tek bir kayıtlı sütun yerine ilişkili
kayıtlardan türetilen bir yaşam döngüsü durumuna göre hesaplar; (3) azaltım
iddialarını yalnızca gerçek bir doğrulanmış referans bulunduğunda üretir,
aksi halde None döner (UI bunu '—' olarak gösterir, asla 0 ya da uydurma bir
sayı değil)."""
from dataclasses import dataclass

from sqlalchemy.orm import Session, selectinload

from app.models.optimization import OptimizationRun
from app.models.production import PhysicalTest, ProductionOrder
from app.models.recipe import PackagingRequest, Recipe
from app.services.carbon import TANIMLANMADI, worst_status
from app.services.common import canonical_packaging_category
from app.services.mass_balance import compute_mass_breakdown

# --- Vaka (case) yaşam döngüsü durumu -------------------------------------
# PackagingRequest.status (Aşama 2-4 içi ilerleme: taslak/degerlendirildi/...)
# ile KARIŞTIRILMAMALI — bu, TÜM akışın (Aşama 1-12) neresinde olduğunu
# ilişkili kayıtlardan türetir; ayrı bir sütun olarak saklanmaz.
TASLAK = "taslak"
OPTIMIZASYONDA = "optimizasyonda"
URETIMDE = "uretimde"
TESTTE = "testte"
TAMAMLANDI = "tamamlandi"


def compute_case_status(db: Session, packaging_request: PackagingRequest) -> str:
    has_verified = (
        db.query(Recipe)
        .filter(Recipe.packaging_request_id == packaging_request.id, Recipe.is_verified.is_(True))
        .first()
        is not None
    )
    if has_verified:
        return TAMAMLANDI

    has_test = (
        db.query(PhysicalTest)
        .join(Recipe, PhysicalTest.recipe_id == Recipe.id)
        .filter(Recipe.packaging_request_id == packaging_request.id)
        .first()
        is not None
    )
    if has_test:
        return TESTTE

    has_order = (
        db.query(ProductionOrder)
        .join(Recipe, ProductionOrder.recipe_id == Recipe.id)
        .filter(Recipe.packaging_request_id == packaging_request.id)
        .first()
        is not None
    )
    if has_order:
        return URETIMDE

    has_optimization = (
        db.query(OptimizationRun)
        .filter(OptimizationRun.packaging_request_id == packaging_request.id)
        .first()
        is not None
    )
    if has_optimization:
        return OPTIMIZASYONDA

    return TASLAK


def count_cases_by_status(db: Session) -> dict[str, int]:
    counts = {TASLAK: 0, OPTIMIZASYONDA: 0, URETIMDE: 0, TESTTE: 0, TAMAMLANDI: 0}
    for req in db.query(PackagingRequest).all():
        counts[compute_case_status(db, req)] += 1
    return counts


# --- Gerçek kütle bazlı toplam kullanım -----------------------------------

@dataclass
class MaterialUsageTotals:
    virgin_kg: float
    pcr_kg: float
    regranul_kg: float

    @property
    def total_kg(self) -> float:
        return self.virgin_kg + self.pcr_kg + self.regranul_kg

    def pct(self, kg: float) -> float:
        return round((kg / self.total_kg) * 100, 1) if self.total_kg > 0 else 0.0


def _order_realized_or_scheduled_qty(order: ProductionOrder) -> float:
    if order.live_data:
        return max(r.produced_qty_units for r in order.live_data)
    return order.scheduled_qty_units or 0


def compute_material_usage_totals(db: Session) -> MaterialUsageTotals:
    """Her vaka (ProductionOrder'ı olan reçete) TAM OLARAK BİR KEZ sayılır —
    aynı optimizasyon koşusunun elenmeyen ama seçilmeyen diğer finalistleri
    dahil edilmez, çünkü onlar için hiç ProductionOrder açılmamıştır."""
    orders = (
        db.query(ProductionOrder)
        .options(
            selectinload(ProductionOrder.recipe).selectinload(Recipe.layers),
            selectinload(ProductionOrder.live_data),
        )
        .all()
    )
    virgin = pcr = regranul = 0.0
    for order in orders:
        recipe = order.recipe
        if recipe is None or not recipe.layers:
            continue
        qty = _order_realized_or_scheduled_qty(order)
        if qty <= 0:
            continue
        packaging_request = recipe.packaging_request
        category = canonical_packaging_category(packaging_request.packaging_type)
        dims = packaging_request.dimensions or {}
        breakdown = compute_mass_breakdown(
            recipe, dims.get("length_mm"), dims.get("width_mm"), category, unit_count=qty
        )
        if breakdown is None:
            continue
        virgin += breakdown.virgin_kg
        pcr += breakdown.pcr_kg
        regranul += breakdown.regranul_kg
    return MaterialUsageTotals(virgin_kg=round(virgin, 2), pcr_kg=round(pcr, 2), regranul_kg=round(regranul, 2))


# --- Gerçekleşen fire + yalnızca referans varsa azaltım iddiası -----------

@dataclass
class RealizedAndGains:
    realized_waste_kg: float
    carbon_reduction_kg_co2: float | None
    prevented_waste_kg: float | None
    # bkz. app/services/carbon.py -- karbon_reduction_kg_co2 None ise anlamsız,
    # değilse "tanimli_demo" olması beklenir (bu sistemde şu an kaynaklı/gerçek
    # bir EF yok) ve UI bunu "DEMO/VARSAYIMSAL EF" ile göstermeli.
    carbon_data_quality: str = TANIMLANMADI


def compute_realized_and_gains(db: Session) -> RealizedAndGains:
    """'Gerçekleşen Fire' her zaman hesaplanır (tüm canlı üretim verisinin
    toplamı). 'Karbon Azaltımı'/'Önlenen Fire' ise YALNIZCA aynı ambalaj
    türünde birden fazla doğrulanmış+üretilmiş reçete varsa hesaplanır —
    ve YALNIZCA en yeni reçete, kendisinden HEMEN ÖNCE doğrulanmış olanla
    karşılaştırılır (her ikisi de doğrulanmışsa birbirini simetrik 'referans'
    sayıp katkıların birbirini götürmesini önlemek için)."""
    orders = (
        db.query(ProductionOrder)
        .options(
            selectinload(ProductionOrder.recipe).selectinload(Recipe.layers),
            selectinload(ProductionOrder.live_data),
        )
        .all()
    )

    realized_waste_kg = sum(r.waste_kg for order in orders for r in order.live_data)

    # Doğrulanmış + üretilmiş + canlı verisi olan reçeteleri ambalaj türüne
    # göre grupla (Dashboard 8'deki referans tanımıyla aynı: aynı
    # packaging_type metni).
    groups: dict[str, list[tuple[Recipe, ProductionOrder]]] = {}
    for order in orders:
        recipe = order.recipe
        if recipe is None or not recipe.is_verified or not order.live_data or not recipe.layers:
            continue
        key = recipe.packaging_request.packaging_type
        groups.setdefault(key, []).append((recipe, order))

    carbon_saved_total = 0.0
    waste_saved_total = 0.0
    carbon_reference_found = False
    waste_reference_found = False
    carbon_statuses: list[str] = []

    for items in groups.values():
        if len(items) < 2:
            continue  # bu türde karşılaştırılacak ikinci bir doğrulanmış üretim yok
        items.sort(key=lambda pair: pair[0].created_at)
        (prev_recipe, prev_order), (curr_recipe, curr_order) = items[-2], items[-1]

        qty = _order_realized_or_scheduled_qty(curr_order)
        if qty <= 0:
            continue

        curr_request = curr_recipe.packaging_request
        curr_category = canonical_packaging_category(curr_request.packaging_type)
        curr_dims = curr_request.dimensions or {}
        curr_breakdown = compute_mass_breakdown(
            curr_recipe, curr_dims.get("length_mm"), curr_dims.get("width_mm"), curr_category, qty
        )

        prev_request = prev_recipe.packaging_request
        prev_category = canonical_packaging_category(prev_request.packaging_type)
        prev_dims = prev_request.dimensions or {}
        prev_breakdown = compute_mass_breakdown(
            prev_recipe, prev_dims.get("length_mm"), prev_dims.get("width_mm"), prev_category, qty
        )

        if curr_breakdown is not None and prev_breakdown is not None:
            carbon_saved_total += prev_breakdown.carbon_kg_co2 - curr_breakdown.carbon_kg_co2
            carbon_reference_found = True
            carbon_statuses.append(curr_breakdown.carbon_ef_status)
            carbon_statuses.append(prev_breakdown.carbon_ef_status)

        prev_qty = sum(r.produced_qty_units for r in prev_order.live_data) or 1
        prev_waste_rate = sum(r.waste_kg for r in prev_order.live_data) / prev_qty
        curr_qty = sum(r.produced_qty_units for r in curr_order.live_data) or 1
        curr_waste_rate = sum(r.waste_kg for r in curr_order.live_data) / curr_qty
        waste_saved_total += (prev_waste_rate - curr_waste_rate) * qty
        waste_reference_found = True

    return RealizedAndGains(
        realized_waste_kg=round(realized_waste_kg, 2),
        carbon_reduction_kg_co2=round(carbon_saved_total, 2) if carbon_reference_found else None,
        prevented_waste_kg=round(waste_saved_total, 2) if waste_reference_found else None,
        carbon_data_quality=worst_status(carbon_statuses) if carbon_statuses else TANIMLANMADI,
    )
