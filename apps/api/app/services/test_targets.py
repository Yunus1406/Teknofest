"""Aşama 11 — fiziksel doğrulama için önerilen test hedefleri.

Önceki hata: Aşama 11'deki hedefler (600 µm / 570-630 µm gibi) reçeteden
BAĞIMSIZ, sabit bir şablondu — reçete 70 µm ise bambaşka bir üründen kalma
şablon gibi görünüyordu. Artık kalınlık ve gramaj hedefleri, reçetenin
GERÇEK toplam kalınlığından (recipe.total_micron) ve ağırlıklı yoğunluğundan
türetilir.

Çekme/uzama/darbe/yırtılma/kaynak gibi mekanik testler için bilgi tabanında
malzeme mekanik özellik verisi (ör. tensile strength) YOK — bu yüzden bu
testler için hedef UYDURULMAZ; yalnızca test yöntemi/standart referansı ve
birim önerilir, target_min/max None bırakılır ve bunun neden böyle olduğu
açıkça belirtilir."""
from dataclasses import dataclass

from app.models.recipe import Recipe
from app.services.mass_balance import weighted_density_kg_m3

# Nominal kalınlık/gramaj etrafında varsayılan kabul toleransı. Gerçek
# üretimde müşteri şartnamesine göre değişebilir — bu bir MVP varsayımıdır.
DEFAULT_TOLERANCE_PCT = 0.10

_TEST_METHODS: dict[str, str] = {
    "kalinlik": "Mikrometre ölçümü (ör. ISO 4593)",
    "gramaj": "Alan tartımı (ör. ISO 536 / ASTM D646)",
    "tensile": "Çekme testi (ör. ISO 527 / ASTM D882)",
    "elongation": "Çekme testi - kopma uzaması (ör. ISO 527 / ASTM D882)",
    "dart_impact": "Serbest düşen dart darbe testi (ör. ASTM D1709)",
    "tear": "Elmendorf yırtılma testi (ör. ISO 6383-2 / ASTM D1922)",
    "seal": "Kaynak dayanım testi (ör. ASTM F88)",
}

_MECHANICAL_TEST_UNITS: dict[str, str] = {
    "tensile": "MPa",
    "elongation": "%",
    "dart_impact": "J",
    "tear": "N",
    "seal": "N/15mm",
}


@dataclass
class SuggestedTestTarget:
    test_type: str
    unit: str
    test_method: str
    nominal_value: float | None
    target_min: float | None
    target_max: float | None
    note: str


def suggested_physical_test_targets(recipe: Recipe) -> list[SuggestedTestTarget]:
    targets: list[SuggestedTestTarget] = []

    if recipe.total_micron:
        nominal = recipe.total_micron
        lo = round(nominal * (1 - DEFAULT_TOLERANCE_PCT), 1)
        hi = round(nominal * (1 + DEFAULT_TOLERANCE_PCT), 1)
        targets.append(
            SuggestedTestTarget(
                test_type="kalinlik",
                unit="µm",
                test_method=_TEST_METHODS["kalinlik"],
                nominal_value=round(nominal, 1),
                target_min=lo,
                target_max=hi,
                note=f"Reçetenin toplam kalınlığı ({nominal:.0f} µm) ±%{DEFAULT_TOLERANCE_PCT*100:.0f} — "
                "müşteri toleransına göre daraltılabilir.",
            )
        )

        density_kg_m3 = weighted_density_kg_m3(recipe)
        if density_kg_m3:
            # gramaj (g/m2) = yoğunluk (kg/m3) * kalınlık (m) * 1000 (kg->g)
            gramaj_nominal = density_kg_m3 * (nominal / 1_000_000.0) * 1000.0
            targets.append(
                SuggestedTestTarget(
                    test_type="gramaj",
                    unit="g/m²",
                    test_method=_TEST_METHODS["gramaj"],
                    nominal_value=round(gramaj_nominal, 2),
                    target_min=round(gramaj_nominal * (1 - DEFAULT_TOLERANCE_PCT), 2),
                    target_max=round(gramaj_nominal * (1 + DEFAULT_TOLERANCE_PCT), 2),
                    note=(
                        "Alansal gramaj (g/m²) — ambalaj başına toplam ağırlık DEĞİL; "
                        "ambalaj başına ağırlık için Aşama 12'deki kütle dengesine bakın."
                    ),
                )
            )

    for test_type, unit in _MECHANICAL_TEST_UNITS.items():
        targets.append(
            SuggestedTestTarget(
                test_type=test_type,
                unit=unit,
                test_method=_TEST_METHODS[test_type],
                nominal_value=None,
                target_min=None,
                target_max=None,
                note=(
                    "Bilgi tabanında bu malzeme kombinasyonu için mekanik özellik verisi "
                    "olmadığından hedef otomatik hesaplanamıyor; laboratuvar/şartname "
                    "referans değeri elle girilmelidir."
                ),
            )
        )

    return targets
