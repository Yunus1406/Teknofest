"""Kütle dengesi hesaplamaları — 'X kg / 1000 ambalaj' gibi tüm fiziksel
kaynak kullanımı figürleri buradan geçer.

Önceki hata: virgin/PCR/regranül kullanımı YÜZDE olarak (0-100) hesaplanıp
metrik tablosuna öyle yazılıyordu; Aşama 12 (finalize) bu yüzdeleri doğrudan
'kg' etiketiyle 10 ile çarpıyordu (`%62 * 10 = 620 "kg"`) — birim hatası,
sonuç gerçek kütleden ~1-2 büyüklük mertebesi sapıyordu. Karbon da benzer
şekilde bir yoğunluk katsayısını (kg CO2/kg) toplam kütleymiş gibi ölçekliyordu.

Burada gerçek fizik kullanılır: kütle = alan × kalınlık × yoğunluk (×
ambalajın kaç 'yüzeyden' oluştuğu — düz bir tabak/kap tek yüzey, esnek bir
film poşeti iki yüzey/panel dikişli kabul edilir).

BASİTLEŞTİRME (dokümante edilmiş MVP varsayımı): şişe/kapak gibi 3 boyutlu
enjeksiyon/üfleme parçalarında gerçek hacim yerine 'düzlemsel eşdeğer' alan
kullanılır (uzunluk × genişlik × et kalınlığı × yoğunluk). Bu, gerçek CAD
hacim hesabı kadar kesin değildir ama sabit bir kütle-yüzde karışımından çok
daha doğrudur ve ileride gerçek hacim verisiyle değiştirilebilir bir tek
nokta (`unit_mass_kg`) sunar.
"""
from dataclasses import dataclass

from app.models.recipe import Recipe
from app.services.carbon import TANIMLANMADI, resolve_carbon_ef, worst_status

# Ambalaj kategorisine göre kaç 'panel/yüzey'den oluştuğu kabul edilir.
# Esnek film ambalaj (poşet/torba): ön+arka panel kaynaklı, iki katman yüzeyi.
# Diğerleri (tabak/bardak/kap/şişe/kapak): tek kabuk yüzeyi kabul edilir.
_SIDED_CATEGORIES: dict[str, int] = {
    "esnek_film_ambalaj": 2,
}
_DEFAULT_SIDES = 1


@dataclass(frozen=True)
class MassBreakdown:
    unit_mass_kg: float
    total_mass_kg: float
    virgin_kg: float
    pcr_kg: float
    regranul_kg: float
    carbon_kg_co2: float
    density_kg_m3: float
    area_m2: float
    thickness_m: float
    sides: int
    # bkz. app/services/carbon.py -- reçetedeki en az güvenilir EF durumu.
    # UI (Dashboard 12) bunu "DEMO/VARSAYIMSAL EF" ya da "EF TANIMLANMADI"
    # rozetiyle göstermeli, karbon_kg_co2'yi asla etiketsiz sunmamalı.
    carbon_ef_status: str = TANIMLANMADI


def weighted_density_kg_m3(recipe: Recipe) -> float | None:
    """Katman kalınlığı + katman-içi oran ile ağırlıklandırılmış ortalama
    yoğunluk. Bir malzemenin density_g_cm3'ü eksikse (ör. bazı PET
    varyantlarında MFI gibi) o satır 0 yoğunlukla değil, atlanarak
    hesaplanır — aksi halde ortalama yanlışlıkla düşük çıkar."""
    total_micron = recipe.total_micron or sum(l.thickness_micron for l in {l.layer_index: l for l in recipe.layers}.values())
    if not total_micron:
        return None
    acc = 0.0
    known_weight = 0.0
    for layer in recipe.layers:
        if layer.material.density_g_cm3 is None:
            continue
        weight = (layer.thickness_micron / total_micron) * (layer.ratio_pct / 100.0)
        acc += weight * layer.material.density_g_cm3
        known_weight += weight
    if known_weight <= 0:
        return None
    # known_weight < 1.0 olabilir (bazı satırlar density'siz atlandıysa) —
    # bilinenler üzerinden normalize et.
    return (acc / known_weight) * 1000.0  # g/cm3 -> kg/m3


def sided_factor(canonical_category: str) -> int:
    return _SIDED_CATEGORIES.get(canonical_category, _DEFAULT_SIDES)


def unit_area_m2(length_mm: float | None, width_mm: float | None) -> float | None:
    if not length_mm or not width_mm:
        return None
    return (length_mm / 1000.0) * (width_mm / 1000.0)


def compute_unit_mass_kg(
    recipe: Recipe, length_mm: float | None, width_mm: float | None, canonical_category: str
) -> float | None:
    """Tek bir ambalajın gerçek kütlesi (kg). Ölçü veya yoğunluk verisi
    eksikse None döner — asla varsayılan/uydurma bir değere düşmez."""
    if not recipe.total_micron:
        return None
    area = unit_area_m2(length_mm, width_mm)
    if area is None:
        return None
    density = weighted_density_kg_m3(recipe)
    if density is None:
        return None
    thickness_m = recipe.total_micron / 1_000_000.0
    return area * thickness_m * density * sided_factor(canonical_category)


def compute_mass_breakdown(
    recipe: Recipe,
    length_mm: float | None,
    width_mm: float | None,
    canonical_category: str,
    unit_count: float,
) -> MassBreakdown | None:
    """`unit_count` adet ambalaj için toplam kütle dengesi. Kompozisyon
    (virgin/PCR/regranül payı) katman verisinden doğrudan, ağırlıklı olarak
    hesaplanır (Aşama 6'daki candidate.weighted_composition_pct ile aynı
    mantık — ama burada gerçek kg'a çevrilir, yüzde olarak bırakılmaz)."""
    unit_mass = compute_unit_mass_kg(recipe, length_mm, width_mm, canonical_category)
    if unit_mass is None:
        return None

    total_micron = recipe.total_micron or 1.0
    composition_kg = {"virgin": 0.0, "pcr": 0.0, "regranul": 0.0}
    carbon_weighted_sum = 0.0  # kg CO2/kg (yoğunluk-ağırlıklı değil, kütle-ağırlıklı)
    ef_statuses: list[str] = []
    for layer in recipe.layers:
        layer_weight = (layer.thickness_micron / total_micron) * (layer.ratio_pct / 100.0)
        mat_type = layer.material.material_type
        mat_mass_kg = layer_weight * unit_mass * unit_count
        composition_kg[mat_type] = composition_kg.get(mat_type, 0.0) + mat_mass_kg
        carbon_value, carbon_status, _source = resolve_carbon_ef(layer.material)
        carbon_weighted_sum += layer_weight * carbon_value
        ef_statuses.append(carbon_status)

    total_mass_kg = unit_mass * unit_count
    density = weighted_density_kg_m3(recipe) or 0.0
    area = unit_area_m2(length_mm, width_mm) or 0.0
    return MassBreakdown(
        unit_mass_kg=unit_mass,
        total_mass_kg=total_mass_kg,
        virgin_kg=composition_kg.get("virgin", 0.0),
        pcr_kg=composition_kg.get("pcr", 0.0),
        regranul_kg=composition_kg.get("regranul", 0.0),
        carbon_kg_co2=carbon_weighted_sum * total_mass_kg,
        density_kg_m3=density,
        area_m2=area,
        thickness_m=recipe.total_micron / 1_000_000.0,
        sides=sided_factor(canonical_category),
        carbon_ef_status=worst_status(ef_statuses),
    )
