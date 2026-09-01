"""Bilgi Tabanı yükleyici: data/*.yaml dosyalarını okuyup DB'ye idempotent
şekilde (var olanı günceller, yoksa oluşturur) yazar. `seed_demo.py` bunu
çağırır; ayrıca API başlangıcında da tetiklenebilir."""
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.models.chemical_restriction import ChemicalRestriction
from app.models.cost_reference import BenchmarkReference, CostReferenceFactor
from app.models.food_contact_requirement import FoodContactRequirement
from app.models.knowledge import (
    Additive,
    CarbonEmissionFactor,
    Material,
    PcrMaterial,
    PirMaterial,
    Polymer,
    Regulation,
)
from app.models.mechanical_test_standard import MechanicalTestStandard
from app.models.recyclability_criterion import RecyclabilityCriterion
from app.models.regulation_requirement import RegulationRequirement
from app.models.technical_reference import (
    LayerStructureReference,
    PolymerTechnicalReference,
    ProcessReference,
)

_MATERIAL_CLASS_BY_TYPE: dict[str, type[Material]] = {
    "virgin": Material,
    "pcr": PcrMaterial,
    "regranul": PirMaterial,
}

DATA_DIR = Path(__file__).resolve().parent / "data"


def _load_yaml(name: str) -> list[dict]:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def load_polymers(db: Session) -> dict[str, str]:
    """Döner: {polymer_code: polymer_id}"""
    code_to_id: dict[str, str] = {}
    for row in _load_yaml("polymers.yaml"):
        existing = db.query(Polymer).filter_by(code=row["code"]).one_or_none()
        if existing:
            existing.name = row["name"]
            existing.category = row["category"]
            existing.base_properties = row.get("base_properties", {})
            obj = existing
        else:
            obj = Polymer(
                code=row["code"],
                name=row["name"],
                category=row["category"],
                base_properties=row.get("base_properties", {}),
            )
            db.add(obj)
        db.flush()
        code_to_id[row["code"]] = obj.id
    return code_to_id


def load_carbon_emission_factors(db: Session) -> dict[str, str]:
    """Döner: {material_key: carbon_emission_factor_id}. Karbon Veri
    Kütüphanesi'ni (bkz. app/services/carbon.py) yükler — bu fazda TÜM
    kayıtlar is_demo_placeholder=True'dur, gerçek bir LCA veritabanı
    entegrasyonu yoktur."""
    key_to_id: dict[str, str] = {}
    for row in _load_yaml("carbon_emission_factors.yaml"):
        existing = db.query(CarbonEmissionFactor).filter_by(material_key=row["material_key"]).one_or_none()
        fields = dict(
            material_key=row["material_key"],
            factor_type=row.get("factor_type", "malzeme"),
            ef_value=row["ef_value"],
            unit=row.get("unit", "kg_co2e_per_kg"),
            source=row["source"],
            year=row.get("year"),
            geography=row.get("geography"),
            version=row.get("version"),
            is_demo_placeholder=row.get("is_demo_placeholder", True),
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            obj = existing
        else:
            obj = CarbonEmissionFactor(**fields)
            db.add(obj)
        db.flush()
        key_to_id[row["material_key"]] = obj.id
    return key_to_id


def load_materials(
    db: Session, polymer_code_to_id: dict[str, str], carbon_ef_key_to_id: dict[str, str] | None = None
) -> dict[str, str]:
    """Döner: {material_name: material_id}. material_type'a göre doğru
    polymorphic alt sınıf (Material/PcrMaterial/PirMaterial) örneklenir —
    PCR ve PIR ASLA aynı Python sınıfına yazılmaz (bkz. app/models/knowledge.py)."""
    carbon_ef_key_to_id = carbon_ef_key_to_id or {}
    name_to_id: dict[str, str] = {}
    for row in _load_yaml("materials.yaml"):
        polymer_id = polymer_code_to_id[row["polymer_code"]]
        material_type = row["material_type"]
        model_cls = _MATERIAL_CLASS_BY_TYPE.get(material_type, Material)

        existing = db.query(Material).filter_by(name=row["name"]).one_or_none()

        base_fields = dict(
            polymer_id=polymer_id,
            name=row["name"],
            material_type=material_type,
            manufacturer=row.get("manufacturer"),
            supplier=row.get("supplier"),
            color=row.get("color"),
            certification_status=row.get("certification_status"),
            suitable_layer_position=row.get("suitable_layer_position"),
            mfi_g_10min=row.get("mfi_g_10min"),
            density_g_cm3=row.get("density_g_cm3"),
            degradation_factor=row.get("degradation_factor", 0.0),
            tensile_strength_mpa=row.get("tensile_strength_mpa"),
            elongation_pct=row.get("elongation_pct"),
            dart_impact_g=row.get("dart_impact_g"),
            melt_temp_c=row.get("melt_temp_c"),
            processing_temp_c=row.get("processing_temp_c"),
            additive_content_note=row.get("additive_content_note"),
            food_contact_eligible=row.get("food_contact_eligible", True),
            max_recommended_ratio_pct=row.get("max_recommended_ratio_pct", 100.0),
            cost_per_kg=row.get("cost_per_kg", 0.0),
            carbon_factor_kg_co2_per_kg=row.get("carbon_factor_kg_co2_per_kg", 0.0),
            carbon_ef_id=carbon_ef_key_to_id.get(row["name"]),
            stock_qty_kg=row.get("stock_qty_kg"),
            lot_number=row.get("lot_number"),
        )
        type_fields: dict = {}
        if material_type == "pcr":
            type_fields = dict(
                contamination_level=row.get("contamination_level"),
                odor_level=row.get("odor_level"),
                technical_constraints=row.get("technical_constraints"),
            )
        elif material_type == "regranul":
            type_fields = dict(
                source_process=row.get("source_process"),
                production_date=row.get("production_date"),
                source_machine_id=row.get("source_machine_id"),
                source_recipe_id=row.get("source_recipe_id"),
            )

        if existing:
            for k, v in {**base_fields, **type_fields}.items():
                setattr(existing, k, v)
            obj = existing
        else:
            obj = model_cls(**base_fields, **type_fields)
            db.add(obj)
        db.flush()
        name_to_id[row["name"]] = obj.id
    return name_to_id


def load_additives(db: Session, carbon_ef_key_to_id: dict[str, str] | None = None) -> dict[str, str]:
    carbon_ef_key_to_id = carbon_ef_key_to_id or {}
    name_to_id: dict[str, str] = {}
    for row in _load_yaml("additives.yaml"):
        existing = db.query(Additive).filter_by(name=row["name"]).one_or_none()
        fields = dict(
            name=row["name"],
            additive_type=row["additive_type"],
            manufacturer=row.get("manufacturer"),
            carrier_polymer=row.get("carrier_polymer"),
            regulatory_document_ref=row.get("regulatory_document_ref"),
            effects=row.get("effects", {}),
            dosage_min_pct=row.get("dosage_min_pct", 0.0),
            dosage_max_pct=row.get("dosage_max_pct", 2.0),
            food_contact_eligible=row.get("food_contact_eligible", True),
            cost_per_kg=row.get("cost_per_kg", 0.0),
            carbon_ef_id=carbon_ef_key_to_id.get(row.get("carbon_key", row["name"])),
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            obj = existing
        else:
            obj = Additive(**fields)
            db.add(obj)
        db.flush()
        name_to_id[row["name"]] = obj.id
    return name_to_id


def load_food_contact_requirements(db: Session, regulation_ids: dict[str, str]) -> int:
    """Faz F.3 — Gıda Temas Mevzuatı Kütüphanesi. Doğal anahtar
    (regulation_id, requirement_type, substance) ile upsert edilir."""
    rows = _load_yaml("food_contact_requirements.yaml")
    count = 0
    for row in rows:
        regulation_id = regulation_ids.get(row["regulation_code"])
        if regulation_id is None:
            continue
        existing = (
            db.query(FoodContactRequirement)
            .filter_by(regulation_id=regulation_id, requirement_type=row["requirement_type"], substance=row.get("substance"))
            .one_or_none()
        )
        fields = dict(
            regulation_id=regulation_id,
            requirement_type=row["requirement_type"],
            substance=row.get("substance"),
            limit_value=row.get("limit_value"),
            limit_unit=row.get("limit_unit"),
            applies_to_pcr=row.get("applies_to_pcr", False),
            notes=row.get("notes", "").strip() if row.get("notes") else None,
            source=row.get("source"),
            year=row.get("year"),
            version=row.get("version", "1.0"),
            is_demo_placeholder=row.get("is_demo_placeholder", True),
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(FoodContactRequirement(**fields))
        count += 1
    db.flush()
    return count


def load_polymer_technical_references(db: Session, polymer_code_to_id: dict[str, str]) -> int:
    """Faz F.5 — Polimer Teknik Referans Kütüphanesi. Doğal anahtar
    (polymer_id, property_name) ile upsert edilir."""
    rows = _load_yaml("polymer_technical_reference.yaml")
    count = 0
    for row in rows:
        polymer_id = polymer_code_to_id.get(row["polymer_code"])
        if polymer_id is None:
            continue
        existing = (
            db.query(PolymerTechnicalReference)
            .filter_by(polymer_id=polymer_id, property_name=row["property_name"])
            .one_or_none()
        )
        fields = dict(
            polymer_id=polymer_id,
            property_name=row["property_name"],
            typical_min=row.get("typical_min"),
            typical_max=row.get("typical_max"),
            unit=row["unit"],
            source=row.get("source"),
            year=row.get("year"),
            version=row.get("version", "1.0"),
            is_demo_placeholder=row.get("is_demo_placeholder", True),
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(PolymerTechnicalReference(**fields))
        count += 1
    db.flush()
    return count


def load_process_references(db: Session) -> int:
    """Faz F.7 — Proses Referans Kütüphanesi. Doğal anahtar
    (process_type, parameter_name) ile upsert edilir."""
    rows = _load_yaml("process_reference.yaml")
    count = 0
    for row in rows:
        existing = (
            db.query(ProcessReference)
            .filter_by(process_type=row["process_type"], parameter_name=row["parameter_name"])
            .one_or_none()
        )
        fields = dict(
            process_type=row["process_type"],
            parameter_name=row["parameter_name"],
            typical_min=row.get("typical_min"),
            typical_max=row.get("typical_max"),
            unit=row["unit"],
            source=row.get("source"),
            year=row.get("year"),
            version=row.get("version", "1.0"),
            is_demo_placeholder=row.get("is_demo_placeholder", True),
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(ProcessReference(**fields))
        count += 1
    db.flush()
    return count


def load_layer_structure_references(db: Session) -> int:
    """Faz F.8 — Ambalaj Yapısı Referans Kütüphanesi. Doğal anahtar
    `structure_pattern` (model üzerinde zaten unique) ile upsert edilir."""
    rows = _load_yaml("layer_structure_reference.yaml")
    count = 0
    for row in rows:
        existing = db.query(LayerStructureReference).filter_by(structure_pattern=row["structure_pattern"]).one_or_none()
        fields = dict(
            structure_pattern=row["structure_pattern"],
            typical_usage=row["typical_usage"].strip(),
            barrier_properties=row["barrier_properties"].strip(),
            source=row.get("source"),
            year=row.get("year"),
            version=row.get("version", "1.0"),
            is_demo_placeholder=row.get("is_demo_placeholder", True),
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(LayerStructureReference(**fields))
        count += 1
    db.flush()
    return count


def load_mechanical_test_standards(db: Session) -> int:
    """Faz F.6 — Mekanik Test Standartları Kütüphanesi. Doğal anahtar
    (test_type, packaging_category) ile upsert edilir."""
    rows = _load_yaml("mechanical_test_standard.yaml")
    count = 0
    for row in rows:
        existing = (
            db.query(MechanicalTestStandard)
            .filter_by(test_type=row["test_type"], packaging_category=row.get("packaging_category"))
            .one_or_none()
        )
        fields = dict(
            test_type=row["test_type"],
            standard_name=row["standard_name"],
            unit=row["unit"],
            packaging_category=row.get("packaging_category"),
            typical_min=row.get("typical_min"),
            typical_max=row.get("typical_max"),
            source=row.get("source"),
            year=row.get("year"),
            version=row.get("version", "1.0"),
            is_demo_placeholder=row.get("is_demo_placeholder", True),
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(MechanicalTestStandard(**fields))
        count += 1
    db.flush()
    return count


def load_recyclability_criteria(db: Session) -> int:
    """Faz F.9 — Geri Dönüştürülebilirlik Değerlendirme Kriterleri. Doğal
    anahtar (packaging_category, dimension) ile upsert edilir."""
    rows = _load_yaml("recyclability_criteria.yaml")
    count = 0
    for row in rows:
        existing = (
            db.query(RecyclabilityCriterion)
            .filter_by(packaging_category=row.get("packaging_category"), dimension=row["dimension"])
            .one_or_none()
        )
        fields = dict(
            packaging_category=row.get("packaging_category"),
            dimension=row["dimension"],
            criterion_text=row["criterion_text"].strip(),
            weight_pct=row.get("weight_pct"),
            source=row.get("source"),
            year=row.get("year"),
            version=row.get("version", "1.0"),
            is_demo_placeholder=row.get("is_demo_placeholder", True),
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(RecyclabilityCriterion(**fields))
        count += 1
    db.flush()
    return count


def load_cost_reference_factors(db: Session) -> int:
    """Faz F.10 — Maliyet Referans Kütüphanesi. Doğal anahtar `cost_type`
    (model üzerinde zaten unique) ile upsert edilir."""
    rows = _load_yaml("cost_reference_factor.yaml")
    count = 0
    for row in rows:
        existing = db.query(CostReferenceFactor).filter_by(cost_type=row["cost_type"]).one_or_none()
        fields = dict(
            cost_type=row["cost_type"],
            typical_min=row.get("typical_min"),
            typical_max=row.get("typical_max"),
            unit=row["unit"],
            currency=row.get("currency", "TRY"),
            source=row.get("source"),
            year=row.get("year"),
            geography=row.get("geography"),
            version=row.get("version", "1.0"),
            is_demo_placeholder=row.get("is_demo_placeholder", True),
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(CostReferenceFactor(**fields))
        count += 1
    db.flush()
    return count


def load_benchmark_references(db: Session) -> int:
    """Faz F.11 — Benchmark/Sektör Karşılaştırma Verisi. Dosya KASITLI OLARAK
    boş -- gerçek bir sektör kaynağı bulunana kadar 0 satır yüklenir (bkz.
    knowledge_base/data/benchmark_reference.yaml)."""
    rows = _load_yaml("benchmark_reference.yaml")
    count = 0
    for row in rows:
        existing = (
            db.query(BenchmarkReference)
            .filter_by(packaging_category=row.get("packaging_category"), metric_name=row["metric_name"])
            .one_or_none()
        )
        fields = dict(
            packaging_category=row.get("packaging_category"),
            metric_name=row["metric_name"],
            typical_value=row.get("typical_value"),
            unit=row["unit"],
            source=row.get("source"),
            year=row.get("year"),
            version=row.get("version", "1.0"),
            is_demo_placeholder=row.get("is_demo_placeholder", True),
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(BenchmarkReference(**fields))
        count += 1
    db.flush()
    return count


def load_regulations(db: Session) -> dict[str, str]:
    code_to_id: dict[str, str] = {}
    for row in _load_yaml("regulations.yaml"):
        existing = db.query(Regulation).filter_by(code=row["code"]).one_or_none()
        fields = dict(
            code=row["code"],
            title=row["title"],
            category=row["category"],
            description=row["description"].strip(),
            criteria=row.get("criteria", {}),
            applicable_packaging_types=row.get("applicable_packaging_types", []),
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            obj = existing
        else:
            obj = Regulation(**fields)
            db.add(obj)
        db.flush()
        code_to_id[row["code"]] = obj.id
    return code_to_id


def _requirement_natural_key(
    regulation_id: str, article: str, sub_article: str | None, packaging_category: str | None, target_year: int | None
) -> tuple:
    return (regulation_id, article, sub_article, packaging_category, target_year)


def _snapshot_requirement_change(
    old: dict | None, new_version: str, new_threshold: float | None, new_text: str
) -> tuple[str | None, datetime | None, str | None]:
    """Faz L.3 (Madde 16) — eski satır (varsa) ile yeni satır arasında
    version/threshold_value/requirement_text bakımından GERÇEK bir fark
    varsa (`previous_version`, `changed_at`, `change_summary`) döner; fark
    yoksa (ya da eski satır hiç yoksa -- ilk yükleme) üçü de None kalır.
    Uydurma bir "değişiklik" ASLA üretilmez, sadece iki gerçek satır
    karşılaştırılır."""
    if old is None:
        return None, None, None
    changed_parts = []
    if old["version"] != new_version:
        changed_parts.append(f"sürüm {old['version']} → {new_version}")
    if old["threshold_value"] != new_threshold:
        changed_parts.append(f"eşik değeri {old['threshold_value']} → {new_threshold}")
    if old["requirement_text"] != new_text:
        changed_parts.append("gereklilik metni güncellendi")
    if not changed_parts:
        return None, None, None
    return old["version"], datetime.now(timezone.utc), "; ".join(changed_parts)


def load_regulation_requirements(db: Session, regulation_ids: dict[str, str]) -> int:
    """PPWR Kural Kütüphanesi (Faz B.8). Kategori+yıl kombinasyonu doğal bir
    eşleşme anahtarı olmadığından (aynı maddenin birden fazla satırı olabilir,
    bkz. PPWR Md.7), idempotentlik 'var olanı güncelle' yerine SİL+YENİDEN
    YAZ ile sağlanır — sadece bu YAML'da geçen regulation_id'lere ait satırlar
    silinir, diğer verilere dokunulmaz.

    Faz L.3 — silmeden ÖNCE her satırın (regulation_id+article+sub_article+
    packaging_category+target_year) doğal anahtarıyla bir STANTAJ (snapshot)
    alınır; yeni satır yazılırken bu snapshot'la karşılaştırılıp GERÇEK bir
    fark varsa `previous_version`/`changed_at`/`change_summary` doldurulur."""
    rows = _load_yaml("regulation_requirements.yaml")
    touched_regulation_ids = {
        regulation_ids[row["regulation_code"]] for row in rows if row["regulation_code"] in regulation_ids
    }
    previous_by_key: dict[tuple, dict] = {}
    if touched_regulation_ids:
        existing = (
            db.query(RegulationRequirement)
            .filter(RegulationRequirement.regulation_id.in_(touched_regulation_ids))
            .all()
        )
        for r in existing:
            key = _requirement_natural_key(r.regulation_id, r.article, r.sub_article, r.packaging_category, r.target_year)
            previous_by_key[key] = {
                "version": r.version,
                "threshold_value": r.threshold_value,
                "requirement_text": r.requirement_text,
            }
        db.query(RegulationRequirement).filter(
            RegulationRequirement.regulation_id.in_(touched_regulation_ids)
        ).delete(synchronize_session=False)
        db.flush()

    count = 0
    for row in rows:
        regulation_id = regulation_ids.get(row["regulation_code"])
        if regulation_id is None:
            continue
        article = row["article"]
        sub_article = row.get("sub_article")
        packaging_category = row.get("packaging_category")
        target_year = row.get("target_year")
        version = row.get("version", "1.0")
        threshold_value = row.get("threshold_value")
        requirement_text = row["requirement_text"].strip()

        key = _requirement_natural_key(regulation_id, article, sub_article, packaging_category, target_year)
        previous_version, changed_at, change_summary = _snapshot_requirement_change(
            previous_by_key.get(key), version, threshold_value, requirement_text
        )

        db.add(
            RegulationRequirement(
                regulation_id=regulation_id,
                regulation_no=row["regulation_no"],
                article=article,
                sub_article=sub_article,
                packaging_category=packaging_category,
                target_year=target_year,
                requirement_text=requirement_text,
                pcr_only=row.get("pcr_only", False),
                exception_text=row.get("exception_text"),
                effective_date=_parse_date(row.get("effective_date")),
                version=version,
                source=row.get("source"),
                default_verdict=row.get("default_verdict", "inceleme_gerekli"),
                threshold_value=threshold_value,
                threshold_unit=row.get("threshold_unit"),
                last_reviewed_at=_parse_date(row.get("last_reviewed_at")),
                previous_version=previous_version,
                changed_at=changed_at,
                change_summary=change_summary,
            )
        )
        count += 1
    db.flush()
    return count


def load_chemical_restrictions(db: Session, regulation_ids: dict[str, str]) -> int:
    """Faz F.4 — Kimyasal Kısıtlar Kütüphanesi. Doğal anahtar
    (substance_group, restriction_type) ile upsert edilir (ör. PFAS'ın
    "tekil_madde_siniri" satırı her zaman aynı satırdır)."""
    rows = _load_yaml("chemical_restrictions.yaml")
    count = 0
    for row in rows:
        existing = (
            db.query(ChemicalRestriction)
            .filter_by(substance_group=row["substance_group"], restriction_type=row["restriction_type"])
            .one_or_none()
        )
        fields = dict(
            substance_group=row["substance_group"],
            restriction_type=row["restriction_type"],
            limit_value=row["limit_value"],
            limit_unit=row["limit_unit"],
            food_contact_only=row.get("food_contact_only", True),
            regulation_id=regulation_ids.get(row.get("regulation_code")),
            source=row.get("source"),
            year=row.get("year"),
            version=row.get("version", "1.0"),
            is_demo_placeholder=row.get("is_demo_placeholder", True),
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(ChemicalRestriction(**fields))
        count += 1
    db.flush()
    return count


def load_all(db: Session) -> dict[str, dict[str, str]]:
    polymer_ids = load_polymers(db)
    carbon_ef_ids = load_carbon_emission_factors(db)
    material_ids = load_materials(db, polymer_ids, carbon_ef_ids)
    additive_ids = load_additives(db, carbon_ef_ids)
    regulation_ids = load_regulations(db)
    load_regulation_requirements(db, regulation_ids)
    load_chemical_restrictions(db, regulation_ids)
    load_food_contact_requirements(db, regulation_ids)
    load_polymer_technical_references(db, polymer_ids)
    load_process_references(db)
    load_layer_structure_references(db)
    load_mechanical_test_standards(db)
    load_recyclability_criteria(db)
    load_cost_reference_factors(db)
    load_benchmark_references(db)
    db.commit()
    return {
        "polymers": polymer_ids,
        "carbon_emission_factors": carbon_ef_ids,
        "materials": material_ids,
        "additives": additive_ids,
        "regulations": regulation_ids,
    }
