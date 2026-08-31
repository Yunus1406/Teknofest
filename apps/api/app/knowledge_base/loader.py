"""Bilgi Tabanı yükleyici: data/*.yaml dosyalarını okuyup DB'ye idempotent
şekilde (var olanı günceller, yoksa oluşturur) yazar. `seed_demo.py` bunu
çağırır; ayrıca API başlangıcında da tetiklenebilir."""
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.models.knowledge import (
    Additive,
    CarbonEmissionFactor,
    Material,
    PcrMaterial,
    PirMaterial,
    Polymer,
    Regulation,
)
from app.models.regulation_requirement import RegulationRequirement

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


def load_regulation_requirements(db: Session, regulation_ids: dict[str, str]) -> int:
    """PPWR Kural Kütüphanesi (Faz B.8). Kategori+yıl kombinasyonu doğal bir
    eşleşme anahtarı olmadığından (aynı maddenin birden fazla satırı olabilir,
    bkz. PPWR Md.7), idempotentlik 'var olanı güncelle' yerine SİL+YENİDEN
    YAZ ile sağlanır — sadece bu YAML'da geçen regulation_id'lere ait satırlar
    silinir, diğer verilere dokunulmaz."""
    rows = _load_yaml("regulation_requirements.yaml")
    touched_regulation_ids = {
        regulation_ids[row["regulation_code"]] for row in rows if row["regulation_code"] in regulation_ids
    }
    if touched_regulation_ids:
        db.query(RegulationRequirement).filter(
            RegulationRequirement.regulation_id.in_(touched_regulation_ids)
        ).delete(synchronize_session=False)
        db.flush()

    count = 0
    for row in rows:
        regulation_id = regulation_ids.get(row["regulation_code"])
        if regulation_id is None:
            continue
        db.add(
            RegulationRequirement(
                regulation_id=regulation_id,
                regulation_no=row["regulation_no"],
                article=row["article"],
                packaging_category=row.get("packaging_category"),
                target_year=row.get("target_year"),
                requirement_text=row["requirement_text"].strip(),
                pcr_only=row.get("pcr_only", False),
                exception_text=row.get("exception_text"),
                effective_date=_parse_date(row.get("effective_date")),
                version=row.get("version", "1.0"),
                source=row.get("source"),
                default_verdict=row.get("default_verdict", "inceleme_gerekli"),
            )
        )
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
    db.commit()
    return {
        "polymers": polymer_ids,
        "carbon_emission_factors": carbon_ef_ids,
        "materials": material_ids,
        "additives": additive_ids,
        "regulations": regulation_ids,
    }
