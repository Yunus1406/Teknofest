"""Aşama 8-12 orkestrasyonu. Aşama 8 (karşılaştırma) ve versiyonlama mantığı
(Aşama 11) gerçek hesaplarla çalışır; Aşama 9-10'daki makine/canlı üretim
verisi bu fazda MOCK/simüle edilir — şema gerçek entegrasyona hazırdır."""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.enums import (
    DataSourceType,
    MetricType,
    PhysicalTestResult,
    ProductionOrderStatus,
    RecipeSource,
    WasteType,
)
from app.models.production import (
    PhysicalTest,
    ProductionLiveData,
    ProductionOrder,
    SustainabilityResult,
    WasteRecord,
)
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.carbon import resolve_carbon_ef, worst_status
from app.services.common import canonical_packaging_category
from app.services.mass_balance import compute_mass_breakdown


# --- Aşama 8: Mevcut ↔ Önerilen Karşılaştırması ---------------------------

def _layer_breakdown(recipe: Recipe) -> list[dict]:
    """Faz B.3 — Dashboard 8'de de 'PCR hangi katmanda?' sorusuna yanıt
    verebilmek için katman bazlı kırılım (bkz. schemas/dashboard.py
    LayerCompositionOut). Aynı layer_index'i paylaşan birden fazla malzeme
    satırı (blend) tek bir katman girdisinde toplanır."""
    by_index: dict[int, dict] = {}
    for layer in sorted(recipe.layers, key=lambda l: l.layer_index):
        entry = by_index.setdefault(
            layer.layer_index,
            {"layer_index": layer.layer_index, "layer_label": layer.layer_label,
             "thickness_micron": layer.thickness_micron, "materials": []},
        )
        entry["materials"].append(
            {
                "material_id": layer.material_id,
                "material_name": layer.material.name,
                "material_type": layer.material.material_type,
                "ratio_pct": layer.ratio_pct,
            }
        )
    return list(by_index.values())


def _composition_side(label: str, recipe: Recipe, is_estimated: bool) -> dict:
    metrics = {m.metric_type: m.value for m in recipe.metrics}
    carbon_status = worst_status([resolve_carbon_ef(layer.material)[1] for layer in recipe.layers])
    return {
        "label": label,
        "virgin_pct": metrics.get("virgin_kullanimi", 0.0),
        "pcr_pct": metrics.get("pcr_kullanimi", 0.0),
        "regranule_pct": metrics.get("regranul_kullanimi", 0.0),
        "total_micron": recipe.total_micron or 0.0,
        "cost_per_kg": metrics.get("maliyet", 0.0),
        "carbon_kg_co2_per_kg": metrics.get("karbon", 0.0),
        "carbon_data_quality": carbon_status,
        "is_estimated": is_estimated,
        "layers": _layer_breakdown(recipe),
    }


def build_comparison(db: Session, recommended_recipe: Recipe) -> dict:
    reference = (
        db.query(Recipe)
        .join(PackagingRequest)
        .filter(
            PackagingRequest.packaging_type == recommended_recipe.packaging_request.packaging_type,
            Recipe.is_verified.is_(True),
            Recipe.id != recommended_recipe.id,
        )
        .order_by(Recipe.version.desc())
        .first()
    )
    recommended_side = _composition_side("Önerilen (Tahmini)", recommended_recipe, True)
    reference_side = _composition_side("Mevcut / Referans", reference, False) if reference else None

    gains: dict[str, float] | None = None
    if reference_side:
        gains = {}
        for key, gain_key in [
            ("carbon_kg_co2_per_kg", "karbon_azaltimi_pct"),
            ("cost_per_kg", "maliyet_azaltimi_pct"),
        ]:
            base = reference_side[key]
            new = recommended_side[key]
            gains[gain_key] = round(((base - new) / base) * 100, 1) if base else 0.0
    # Referans yoksa gains None kalır — karşılaştırma temeli olmayan bir
    # azaltım iddia edilmez (bkz. kullanıcı bildirimi #11).

    return {"reference": reference_side, "recommended": recommended_side, "gains": gains}


# --- Aşama 9: Üretime Aktarım ---------------------------------------------

def create_production_order(db: Session, recipe: Recipe, qty_units: int) -> ProductionOrder:
    order = ProductionOrder(
        recipe_id=recipe.id,
        line_id=recipe.line_id,
        status=ProductionOrderStatus.BEKLIYOR.value,
        scheduled_qty_units=qty_units,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


# --- Aşama 10: Canlı Üretim Takibi (SİMÜLE) -------------------------------

TICK_INTERVAL_MINUTES = 5

# Faz B.6 — demo hatlarımız (ekstrüzyon/termoform/enjeksiyon) baskı/laminasyon
# yapmıyor; simülasyon o yüzden sadece gerçekçi olan türleri üretir
# (PRINTING/LAMINATION/CONTAMINATED enum'da tanımlı kalır, gerçek entegrasyon
# ileride bu türleri de üretebilir). Her tür için varsayılan geri
# kazanılabilirlik: temiz proses fire'ı (kenar/bobin/proses ayarı/start-up)
# tipik olarak dahili PIR/regranül hattına döner, kalite reddi genelde dönmez.
WASTE_TYPE_RECOVERABLE_DEFAULT: dict[str, bool] = {
    WasteType.START_UP.value: True,
    WasteType.EDGE_TRIM.value: True,
    WasteType.ROLL_CHANGE.value: True,
    WasteType.QUALITY_REJECT.value: False,
    WasteType.PRINTING.value: False,
    WasteType.LAMINATION.value: False,
    WasteType.CUTTING.value: True,
    WasteType.PROCESS_ADJUSTMENT.value: True,
    WasteType.CONTAMINATED.value: False,
}

_DEMO_OPERATORS = ["Operatör A. Yıldız", "Operatör M. Kaya", "Operatör S. Demir"]


def _waste_type_fractions_for_tick(i: int, ticks: int) -> list[tuple[str, float]]:
    """Tick pozisyonuna göre gerçekçi bir fire türü dağılımı: ilk tick
    start-up ağırlıklı, son tick bobin değişimi ağırlıklı, arada periyodik
    küçük kalite reddi — sabit oranlarla değil, üretim akışının doğasına
    göre (başlangıç/bitiş/ara) değişen bir kırılım."""
    if i == 0:
        return [(WasteType.START_UP.value, 0.65), (WasteType.EDGE_TRIM.value, 0.35)]
    if ticks > 1 and i == ticks - 1:
        return [(WasteType.EDGE_TRIM.value, 0.7), (WasteType.ROLL_CHANGE.value, 0.3)]
    if i % 3 == 2:
        return [(WasteType.EDGE_TRIM.value, 0.8), (WasteType.QUALITY_REJECT.value, 0.2)]
    return [(WasteType.EDGE_TRIM.value, 1.0)]


def _split_amount(total: float, fracs: list[float]) -> list[float]:
    """`total`ı (zaten 3 ondalığa yuvarlı) verilen oranlara böler; son payı
    kalanla doldurarak toplamın TAM OLARAK `total`a eşit kalmasını garanti
    eder (bağımsız yuvarlamalar toplamda sapma yaratabilirdi)."""
    amounts: list[float] = []
    remaining = round(total, 3)
    for frac in fracs[:-1]:
        amt = round(total * frac, 3)
        amounts.append(amt)
        remaining = round(remaining - amt, 3)
    amounts.append(remaining)
    return amounts


def simulate_live_data(db: Session, order: ProductionOrder, ticks: int = 5) -> list[ProductionLiveData]:
    """Gerçek makine entegrasyonu bu fazda yok — üretilen veri, gerçek
    entegrasyonla AYNI ŞEMAYA yazılır (üretim ortamında satır satır PLC/SCADA
    verisiyle doldurulabilir), ama `source='simulasyon_verisi'` ile işaretlenir
    ki 'Makineden Alınan' (gerçek entegrasyon) ile karıştırılmasın.

    Önceki hatalar: (a) tüm satırlar aynı `datetime.now()` anında üretiliyordu
    -> hepsi aynı zaman damgasını taşıyordu; (b) enerji/fire'ın dönemsel mi
    kümülatif mi olduğu belirsizdi. Artık zaman her tick'te ilerliyor ve hem
    dönemsel hem kümülatif değerler ayrı ayrı saklanıyor.

    Faz B.6 — `ProductionLiveData.waste_kg` (dönemsel toplam, DEĞİŞMEDEN
    kalır) her tick'te AYRICA tipli `WasteRecord` satırlarına bölünür; bu iki
    kaynağın toplamı her zaman birebir eşleşir (bkz. test_live_data_
    simulation.py::test_waste_records_reconcile_with_period_waste_kg)."""
    recipe = order.recipe
    rows: list[ProductionLiveData] = []
    waste_records: list[WasteRecord] = []
    produced_so_far = 0
    cumulative_energy = 0.0
    cumulative_waste = 0.0
    per_tick = max(1, order.scheduled_qty_units // ticks) if order.scheduled_qty_units else 100
    base_ts = datetime.now(timezone.utc)

    for i in range(ticks):
        period_qty = per_tick
        produced_so_far = min(produced_so_far + period_qty, order.scheduled_qty_units or produced_so_far + period_qty)
        consumption = {
            layer.material_id: round(period_qty * (layer.ratio_pct / 100.0) * 0.01, 3)
            for layer in recipe.layers
        }
        period_energy = round(per_tick * 0.004 * random.uniform(0.9, 1.1), 3)
        period_waste = round(per_tick * 0.001 * random.uniform(0.5, 1.5), 3)
        cumulative_energy = round(cumulative_energy + period_energy, 3)
        cumulative_waste = round(cumulative_waste + period_waste, 3)
        row_ts = base_ts + timedelta(minutes=TICK_INTERVAL_MINUTES * i)

        row = ProductionLiveData(
            production_order_id=order.id,
            ts=row_ts,
            produced_qty_units=produced_so_far,
            period_produced_qty_units=period_qty,
            material_consumption=consumption,
            line_speed_m_min=round(random.uniform(80, 140), 1),
            energy_kwh=period_energy,
            cumulative_energy_kwh=cumulative_energy,
            waste_kg=period_waste,
            cumulative_waste_kg=cumulative_waste,
            source=DataSourceType.SIMULASYON_VERISI.value,
        )
        db.add(row)
        rows.append(row)

        fracs = _waste_type_fractions_for_tick(i, ticks)
        amounts = _split_amount(period_waste, [f for _, f in fracs])
        for (waste_type, _), amount in zip(fracs, amounts):
            if amount <= 0:
                continue
            waste_records.append(
                WasteRecord(
                    production_order_id=order.id,
                    ts=row_ts,
                    waste_type=waste_type,
                    kg=amount,
                    recoverable=WASTE_TYPE_RECOVERABLE_DEFAULT.get(waste_type, False),
                )
            )
    db.add_all(waste_records)

    # Gerçekleşen katman oranları: reçetenin NOMİNAL oranlarından küçük bir
    # sapmayla (üretimde ölçüm/proses varyasyonu her zaman vardır) — açıkça
    # simülasyon, `order.status`/satır `source` alanı zaten bunu işaretliyor.
    actual_layer_ratios: dict[str, dict[str, float]] = {}
    for layer in recipe.layers:
        key = str(layer.layer_index)
        actual_layer_ratios.setdefault(key, {})
        actual_layer_ratios[key][layer.material_id] = round(
            layer.ratio_pct + random.uniform(-1.5, 1.5), 2
        )

    order.status = ProductionOrderStatus.TAMAMLANDI.value
    order.operator = random.choice(_DEMO_OPERATORS)
    order.actual_start = base_ts
    order.actual_end = base_ts + timedelta(minutes=TICK_INTERVAL_MINUTES * ticks)
    order.downtime_minutes = round(random.uniform(0, 15), 1)
    order.avg_micron = (
        round(recipe.total_micron * random.uniform(0.97, 1.03), 2) if recipe.total_micron else None
    )
    order.actual_layer_ratios = actual_layer_ratios

    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


# --- Aşama 11: Fiziksel Doğrulama -----------------------------------------

def _evaluate_physical_test(t: dict) -> str:
    """Faz D.2 — `PhysicalTestResult` döner. Sadece hem gerçek bir ölçüm
    değeri HEM tanımlı bir kabul kriteri (target_min/target_max'tan en az
    biri) varsa 'basarili'/'basarisiz' kararı verilebilir; ikisi de
    tanımlı değilse (ör. bilgi tabanında bu malzeme kombinasyonu için
    mekanik özellik verisi yok — bkz. test_targets.py) sonuç HER ZAMAN
    'beklemede'dir, ASLA sessizce 'basarili' sayılmaz (eski hata: Tensile=0
    MPa gibi hiç ölçülmemiş/kriteri olmayan testler 'Geçti' görünüyordu)."""
    value = t.get("value")
    target_min = t.get("target_min")
    target_max = t.get("target_max")
    if value is None or (target_min is None and target_max is None):
        return PhysicalTestResult.PENDING.value
    if target_min is not None and value < target_min:
        return PhysicalTestResult.FAILED.value
    if target_max is not None and value > target_max:
        return PhysicalTestResult.FAILED.value
    return PhysicalTestResult.PASSED.value


def submit_physical_tests(
    db: Session, order: ProductionOrder, tests: list[dict]
) -> tuple[list[PhysicalTest], Recipe | None]:
    """Test sonuçlarını kaydeder. Herhangi biri gerçekten BAŞARISIZ ise
    (tanımlı bir aralığın dışında) reçetenin yeni versiyonunu (V(n)->V(n+1))
    taslak olarak oluşturur — tüm geçmiş saklanır. Hiçbiri başarısız
    olmayıp bazıları 'beklemede' (kriter tanımsız) ise reçete henüz
    doğrulanmış SAYILMAZ ama yeni bir versiyon da açılmaz (bu bir reçete
    kusuru değil, bir veri boşluğu). Boş bir test listesi REDDEDİLİR —
    hiç test girilmeden 'doğrulandı' durumu OLUŞAMAZ (bkz. Faz D.2)."""
    if not tests:
        raise ValueError("En az bir fiziksel test sonucu girilmeden doğrulama gönderilemez.")

    rows: list[PhysicalTest] = []
    any_failed = False
    any_pending = False
    for t in tests:
        result = _evaluate_physical_test(t)
        if result == PhysicalTestResult.FAILED.value:
            any_failed = True
        elif result == PhysicalTestResult.PENDING.value:
            any_pending = True
        row = PhysicalTest(
            recipe_id=order.recipe_id,
            production_order_id=order.id,
            test_type=t["test_type"],
            value=t["value"],
            unit=t["unit"],
            target_min=t.get("target_min"),
            target_max=t.get("target_max"),
            test_method=t.get("test_method"),
            result=result,
            passed=(result == PhysicalTestResult.PASSED.value),
            source="laboratuvar_testi",
        )
        db.add(row)
        rows.append(row)

    new_version: Recipe | None = None
    recipe = order.recipe
    if any_failed:
        recipe.status = "revizyon_gerekli"
        new_version = Recipe(
            packaging_request_id=recipe.packaging_request_id,
            version=recipe.version + 1,
            parent_recipe_id=recipe.id,
            line_id=recipe.line_id,
            source=RecipeSource.URETILDI.value,
            status="taslak_optimizasyona_geri_dondu",
        )
        db.add(new_version)
        db.flush()  # new_version.id üretilsin
        for layer in recipe.layers:
            db.add(
                RecipeLayer(
                    recipe_id=new_version.id,
                    layer_index=layer.layer_index,
                    layer_label=layer.layer_label,
                    material_id=layer.material_id,
                    ratio_pct=layer.ratio_pct,
                    thickness_micron=layer.thickness_micron,
                )
            )
    elif any_pending:
        # Kusur değil, veri boşluğu -- doğrulanmış sayılmaz ama versiyon da
        # açılmaz. Bkz. app/services/test_targets.py: hedef otomatik
        # hesaplanamayan mekanik testler (tensile/elongation/dart/tear/seal)
        # için bilgi tabanı zenginleştirilene kadar bu durumda kalınır.
        recipe.status = "fiziksel_dogrulama_bekleniyor"
    else:
        recipe.status = "dogrulandi"

    db.commit()
    for r in rows:
        db.refresh(r)
    return rows, new_version


# --- Aşama 12: Nihai Sonuç ve Sürdürülebilirlik Kazanımı -------------------

def finalize_result(db: Session, recipe: Recipe) -> SustainabilityResult:
    """1.000 satılabilir ambalaj başına GERÇEK kütle dengesi.

    Önceki hata: virgin/PCR/regranül YÜZDE metrikleri (0-100) doğrudan 'kg'
    etiketiyle 10 ile çarpılıyordu, karbon da bir yoğunluk katsayısı (kg
    CO2/kg) 1000 ile çarpılıyordu — ikisi de birim hatasıydı. Artık gerçek
    fizik kullanılır (bkz. app/services/mass_balance.py): alan × kalınlık ×
    yoğunluk × 1000 birim. Ölçü/yoğunluk verisi eksikse alan bazlı figürler
    None döner (uydurma bir sayı asla üretilmez); fire/enerji zaten canlı
    üretim verisinden gerçek kg/kWh olarak hesaplanıyordu, değişmedi.

    Faz D.2 — ÖNCEDEN bu fonksiyon `recipe.is_verified`'ı fiziksel test
    sonucuna HİÇ bakmadan koşulsuz True yapıyordu (gerçek bir bug — Dashboard
    11'de testler başarısız/beklemede olsa bile Dashboard 12'de 'Doğrulandı'
    durumu oluşabiliyordu). Artık en az bir `PhysicalTest` kaydı YOKSA veya
    HERHANGİ biri 'basarili' değilse (başarısız YA DA beklemede) reddedilir."""
    tests = db.query(PhysicalTest).filter_by(recipe_id=recipe.id).all()
    if not tests or any(t.result != PhysicalTestResult.PASSED.value for t in tests):
        raise ValueError(
            "Reçete, tüm fiziksel testler gerçekten başarıyla geçmeden "
            "('Doğrulandı') firma hafızasına kaydedilemez."
        )

    live_rows = (
        db.query(ProductionLiveData)
        .join(ProductionOrder)
        .filter(ProductionOrder.recipe_id == recipe.id)
        .all()
    )
    total_produced = sum(r.produced_qty_units for r in live_rows) or 1
    total_waste = sum(r.waste_kg for r in live_rows)
    total_energy = sum(r.energy_kwh for r in live_rows)

    packaging_request = recipe.packaging_request
    category = canonical_packaging_category(packaging_request.packaging_type)
    dims = packaging_request.dimensions or {}
    breakdown = compute_mass_breakdown(
        recipe,
        length_mm=dims.get("length_mm"),
        width_mm=dims.get("width_mm"),
        canonical_category=category,
        unit_count=1000,
    )

    per_1000 = {
        "virgin_kg": round(breakdown.virgin_kg, 3) if breakdown else None,
        "pcr_kg": round(breakdown.pcr_kg, 3) if breakdown else None,
        "regranul_kg": round(breakdown.regranul_kg, 3) if breakdown else None,
        "karbon_kg_co2": round(breakdown.carbon_kg_co2, 3) if breakdown else None,
        # bkz. app/services/carbon.py -- karbon_kg_co2 hiçbir zaman bu
        # etiket olmadan gösterilmemeli (Dashboard 12).
        "karbon_veri_kalitesi": breakdown.carbon_ef_status if breakdown else None,
        "fire_kg": round((total_waste / total_produced) * 1000, 3) if live_rows else None,
        "enerji_kwh": round((total_energy / total_produced) * 1000, 3) if live_rows else None,
    }
    if breakdown is None:
        per_1000["_uyari"] = (
            "Ölçü (uzunluk/genişlik) veya malzeme yoğunluğu verisi eksik olduğu için "
            "kütle bazlı figürler hesaplanamadı."
        )

    result = SustainabilityResult(recipe_id=recipe.id, per_1000_units=per_1000, is_actual=True)
    db.add(result)
    recipe.is_verified = True
    # Faz B.5: bu case kalıcı bir SKU'yu hedefliyorsa, SKU'nun "o an geçerli
    # doğrulanmış reçetesi" bu olsun -- find_reference_recipe artık bunu
    # kullanır (bkz. packaging_service.py).
    if packaging_request.sku_id and packaging_request.sku:
        packaging_request.sku.current_recipe_id = recipe.id
    db.commit()
    db.refresh(result)
    return result


def version_history(db: Session, recipe: Recipe) -> list[dict]:
    chain: list[dict] = []
    current: Recipe | None = recipe
    while current is not None:
        chain.append(
            {
                "id": current.id,
                "version": current.version,
                "status": current.status,
                "is_verified": current.is_verified,
                "created_at": current.created_at.isoformat(),
            }
        )
        current = db.get(Recipe, current.parent_recipe_id) if current.parent_recipe_id else None
    return list(reversed(chain))
