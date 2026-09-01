"""Faz I.3 — Gerçek Öğrenme Hafızası Mekanizması.

Faz B/G.4'ün firma hafızası "geçmiş doğrulanmış reçeteyi bul ve göster"
seviyesindeydi. Bu modül onu bir NEDENSEL zincire çıkarır: her reçete
versiyonu için "ne değiştirdik" (bir önceki versiyona göre gerçek
kompozisyon farkı) → "hangi hatta" → "hangi hedef proses parametreleriyle"
→ "fire/enerji sonucu ne oldu" (GERÇEK canlı üretim verisinden) →
"fiziksel test sonucu ne oldu" → "doğrulandı mı, revizyon mu gerekti"
birbirine bağlanır. Karmaşık bir ML modeli DEĞİL — yapılandırılmış,
sorgulanabilir bir kayıt zinciri (basit GROUP BY seviyesinde).

ÖNEMLİ dürüstlük notu: bugünkü sistemde bir reçete versiyonu SADECE
fiziksel test başarısız olduğunda oluşur (`production_flow_service.
submit_physical_tests`) ve yeni versiyonun katman/oran verisi ebeveynden
BİREBİR KOPYALANIR (gerçek bir kompozisyon değişikliği üreten bir kod yolu
henüz yok). Yani `diff_recipe_compositions` GERÇEK bir fark verildiğinde
doğru hesaplar, ama bugünkü canlı veride çoğu geçiş dürüstçe "değişiklik
yok" gösterir -- bu bir hata değil, mevcut üretim akışının GERÇEK
yansımasıdır."""
from sqlalchemy.orm import Session

from app.models.infrastructure import ProductionLine
from app.models.production import PhysicalTest, ProductionOrder
from app.models.recipe import Recipe
from app.models.technical_reference import ProcessReference


def diff_recipe_compositions(old: Recipe, new: Recipe) -> list[dict]:
    """İki reçete arasındaki GERÇEK kompozisyon farkını bulur -- katman
    kalınlığı, katman içi malzeme oranı, katkı maddesi dozajı, eklenen/
    kaldırılan katman. Fark yoksa boş liste döner; uydurma bir 'değişiklik'
    ASLA üretilmez."""
    diffs: list[dict] = []

    old_layer_materials: dict[int, dict[str, float]] = {}
    old_thickness: dict[int, float] = {}
    for l in old.layers:
        old_layer_materials.setdefault(l.layer_index, {})[l.material_id] = l.ratio_pct
        old_thickness[l.layer_index] = l.thickness_micron

    new_layer_materials: dict[int, dict[str, float]] = {}
    new_thickness: dict[int, float] = {}
    for l in new.layers:
        new_layer_materials.setdefault(l.layer_index, {})[l.material_id] = l.ratio_pct
        new_thickness[l.layer_index] = l.thickness_micron

    all_indices = sorted(set(old_layer_materials) | set(new_layer_materials))
    for idx in all_indices:
        if idx not in old_layer_materials:
            diffs.append({"tur": "katman_eklendi", "layer_index": idx, "aciklama": f"Katman {idx} eklendi"})
            continue
        if idx not in new_layer_materials:
            diffs.append({"tur": "katman_kaldirildi", "layer_index": idx, "aciklama": f"Katman {idx} kaldırıldı"})
            continue

        old_t, new_t = old_thickness.get(idx), new_thickness.get(idx)
        if old_t != new_t:
            diffs.append(
                {
                    "tur": "kalinlik_degisti", "layer_index": idx, "eski_deger": old_t, "yeni_deger": new_t,
                    "aciklama": f"Katman {idx} kalınlığı {old_t}→{new_t} µm",
                }
            )

        old_mats, new_mats = old_layer_materials[idx], new_layer_materials[idx]
        for material_id in sorted(set(old_mats) | set(new_mats)):
            old_r, new_r = old_mats.get(material_id), new_mats.get(material_id)
            if old_r != new_r:
                diffs.append(
                    {
                        "tur": "malzeme_orani_degisti", "layer_index": idx, "material_id": material_id,
                        "eski_deger": old_r, "yeni_deger": new_r,
                        "aciklama": f"Katman {idx} malzeme oranı %{old_r if old_r is not None else 0}→%{new_r if new_r is not None else 0}",
                    }
                )

    old_additives = {(a.layer_index, a.additive_id): a.dosage_pct for a in old.additives}
    new_additives = {(a.layer_index, a.additive_id): a.dosage_pct for a in new.additives}
    for key in sorted(set(old_additives) | set(new_additives), key=lambda k: (k[0] is None, k[0] or 0, k[1])):
        old_d, new_d = old_additives.get(key), new_additives.get(key)
        if old_d != new_d:
            layer_idx, additive_id = key
            diffs.append(
                {
                    "tur": "katki_maddesi_dozaji_degisti", "layer_index": layer_idx, "additive_id": additive_id,
                    "eski_deger": old_d, "yeni_deger": new_d,
                    "aciklama": f"Katkı maddesi dozajı %{old_d if old_d is not None else 0}→%{new_d if new_d is not None else 0}",
                }
            )

    return diffs


def _target_process_parameters(db: Session, line: ProductionLine | None) -> list[dict]:
    if line is None or not line.process_type:
        return []
    rows = db.query(ProcessReference).filter_by(process_type=line.process_type).all()
    return [
        {"parameter_name": r.parameter_name, "typical_min": r.typical_min, "typical_max": r.typical_max, "unit": r.unit}
        for r in rows
    ]


def causal_chain_for_recipe(db: Session, recipe: Recipe) -> list[dict]:
    """`production_flow_service.version_history()`'nin zenginleştirilmiş
    hali -- onu DEĞİŞTİRMEZ, yanına eklenir. `parent_recipe_id` zincirini
    AYNI şekilde gezer, ama her halka için kompozisyon farkı + hat + hedef
    proses parametreleri + GERÇEK fire/enerji + fiziksel test özeti +
    nihai durumu birleştirir."""
    chain: list[Recipe] = []
    current: Recipe | None = recipe
    while current is not None:
        chain.append(current)
        current = db.get(Recipe, current.parent_recipe_id) if current.parent_recipe_id else None
    chain.reverse()  # en eski -> en yeni

    result: list[dict] = []
    previous: Recipe | None = None
    for node in chain:
        diff = diff_recipe_compositions(previous, node) if previous is not None else None

        line = db.get(ProductionLine, node.line_id) if node.line_id else None

        orders = db.query(ProductionOrder).filter_by(recipe_id=node.id).all()
        live_rows = [r for o in orders for r in o.live_data]
        fire_kg = round(sum(r.waste_kg for r in live_rows), 3) if live_rows else None
        enerji_kwh = round(sum(r.energy_kwh for r in live_rows), 3) if live_rows else None

        tests = db.query(PhysicalTest).filter_by(recipe_id=node.id).all()
        physical_test_summary = {
            "basarili": sum(1 for t in tests if t.result == "basarili"),
            "basarisiz": sum(1 for t in tests if t.result == "basarisiz"),
            "beklemede": sum(1 for t in tests if t.result == "beklemede"),
        }

        result.append(
            {
                "id": node.id,
                "version": node.version,
                "status": node.status,
                "is_verified": node.is_verified,
                "created_at": node.created_at,
                "diff_from_previous": diff,
                "line_name": line.name if line is not None else None,
                "target_process_parameters": _target_process_parameters(db, line),
                "gerceklesen_fire_kg": fire_kg,
                "gerceklesen_enerji_kwh": enerji_kwh,
                "physical_test_summary": physical_test_summary,
            }
        )
        previous = node
    return result


_REVISION_STATUSES = ("revizyon_gerekli", "taslak_optimizasyona_geri_dondu")


def _classify_change(diff: list[dict]) -> str:
    if not diff:
        return "degisiklik_yok"
    types = {d["tur"] for d in diff}
    if "malzeme_orani_degisti" in types:
        return "malzeme_orani_degisimi"
    if "kalinlik_degisti" in types:
        return "kalinlik_degisimi"
    if "katki_maddesi_dozaji_degisti" in types:
        return "katki_maddesi_degisimi"
    if "katman_eklendi" in types or "katman_kaldirildi" in types:
        return "katman_yapisi_degisimi"
    return "diger_degisiklik"


def _transition_outcome(child: Recipe) -> str:
    if child.is_verified:
        return "basarili"
    if child.status in _REVISION_STATUSES:
        return "revizyon_gerekti"
    return "beklemede"


def change_outcome_stats(db: Session) -> dict:
    """Faz I.3 — TÜM reçete versiyon geçişlerini (parent_recipe_id dolu
    olan her reçete) kaba bir 'değişiklik türü'ne göre gruplayıp
    doğrulandı/revizyon-gerekti/beklemede sayılarını sayar. "Bu tür
    değişiklik geçmişte genelde başarılı mı oldu?" sorusuna temel veri
    sağlar -- basit bir GROUP BY, ML modeli DEĞİL.

    Bugünkü sistemde revizyonlar ebeveynden birebir kopyalandığından
    (bkz. modül docstring'i) çoğu geçiş dürüstçe 'degisiklik_yok' grubuna
    düşer -- gerçek kompozisyon değişiklikleri sisteme girdikçe diğer
    gruplar dolmaya başlar."""
    children = db.query(Recipe).filter(Recipe.parent_recipe_id.isnot(None)).all()
    buckets: dict[str, dict[str, int]] = {}
    for child in children:
        parent = db.get(Recipe, child.parent_recipe_id)
        if parent is None:
            continue
        change_type = _classify_change(diff_recipe_compositions(parent, child))
        outcome = _transition_outcome(child)
        bucket = buckets.setdefault(change_type, {"basarili": 0, "revizyon_gerekti": 0, "beklemede": 0})
        bucket[outcome] += 1
    return buckets
