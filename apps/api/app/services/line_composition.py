"""Faz G.3 — Aşama 4'ün "Kayıtlı Makineden Hat Oluştur" özelliği: birden
fazla mevcut `ProductionLine` satırı (her biri tek bir fiziksel ünite/makine
olarak da kaydedilmiş olabilir, ör. bir ekstrüder + bir gravimetrik dozaj +
bir film hattı) seçildiğinde, yeni bileşik hattın teknik değerlerini
seçilenlerden TÜRETİR. Bu fonksiyon KASITLI OLARAK DB'ye dokunmaz (saf/test
edilebilir) -- DB sorgusu çağıran router'da yapılır, sonuç burada işlenir.

Türetme mantığı:
  - min/max_micron: KESİŞİM (zincir sadece TÜM bileşenlerin ortak
    işleyebildiği kalınlık aralığında çalışabilir).
  - line_speed_m_min: bileşenlerin EN YAVAŞININ hızı (bir üretim zinciri
    en yavaş halkası kadar hızlı çalışır).
  - nominal/actual_capacity_kg_year: bileşenlerin EN DÜŞÜĞÜ (darboğaz).
  - pcr_capable/pir_capable: SADECE bilgi taşıyan (None olmayan) bileşenler
    arasında hepsi True ise True, biri False ise False; hiçbiri bilgi
    taşımıyorsa None (uydurma bir kabiliyet iddiası yok).
  - max_pcr/pir_technical_pct: bileşenlerin EN DÜŞÜĞÜ (en kısıtlayıcı limit
    tüm hattı bağlar).
  - suitable_polymer_codes: KESİŞİM (hattın işleyebileceği polimer, sadece
    TÜM bileşenlerin ortak desteklediği aileler).
  - layer_structure: ekstrüzyon sınıflı (process_type'ında "extrusion"
    geçen) bir bileşen varsa ondan; yoksa boş bırakılır (kullanıcı girer).
Tüm türetilen değerler kullanıcı tarafından submit öncesi DÜZENLENEBİLİR --
bu fonksiyon sadece bir başlangıç önerisi üretir, bağlayıcı bir karar değil.
"""
from app.models.infrastructure import ProductionLine


def derive_composite_line_defaults(components: list[ProductionLine]) -> dict:
    if not components:
        return {}

    result: dict = {
        "name": " + ".join(c.name for c in components),
        "component_line_ids": [c.id for c in components],
        "min_micron": max(c.min_micron for c in components),
        "max_micron": min(c.max_micron for c in components),
    }

    speeds = [c.line_speed_m_min for c in components if c.line_speed_m_min]
    if speeds:
        result["line_speed_m_min"] = min(speeds)

    for cap_field in ("nominal_capacity_kg_year", "actual_capacity_kg_year"):
        values = [v for c in components if (v := getattr(c, cap_field)) is not None]
        if values:
            result[cap_field] = min(values)

    for bool_field in ("pcr_capable", "pir_capable"):
        values = [v for c in components if (v := getattr(c, bool_field)) is not None]
        if values:
            result[bool_field] = all(values)

    for pct_field in ("max_pcr_technical_pct", "max_pir_technical_pct"):
        values = [v for c in components if (v := getattr(c, pct_field)) is not None]
        if values:
            result[pct_field] = min(values)

    polymer_sets = [set(c.suitable_polymer_codes) for c in components if c.suitable_polymer_codes]
    if polymer_sets:
        result["suitable_polymer_codes"] = sorted(set.intersection(*polymer_sets))

    extrusion_components = [
        c for c in components if c.process_type and "extrusion" in c.process_type.lower()
    ]
    if extrusion_components:
        result["layer_structure"] = extrusion_components[0].layer_structure
        result["layer_count"] = extrusion_components[0].layer_count

    return result
