"""Jüri demosu için tohum veri: Bilgi Tabanı + 5 örnek üretim hattı (tabak,
esnek film, şişe, kapak, bardak/kap — bkz. app/services/common.py'deki
kanonik ambalaj kategorileri) + hat-malzeme uyumu + birkaç örnek ambalaj
talebi. Script her talebi uçtan uca aşama 3-7'den geçirip hazır birer
optimizasyon sonucu bırakır ki 12 aşamalık akış baştan itibaren gerçek
veriyle, birden fazla ambalaj türü için gezilebilsin.

Çalıştırma:  python -m scripts.seed_demo   (apps/api dizininden)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal, engine  # noqa: E402
from app.knowledge_base.loader import load_all  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.company import Company, Facility  # noqa: E402
from app.models.cost import CostFactor  # noqa: E402
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine  # noqa: E402
from app.models.knowledge import Material  # noqa: E402
from app.models.product_sku import ProductSku  # noqa: E402
from app.services import optimization_service, packaging_service  # noqa: E402


def _upsert_product_sku(db, **fields) -> ProductSku:
    existing = db.query(ProductSku).filter_by(sku_code=fields["sku_code"]).one_or_none()
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        db.flush()
        return existing
    sku = ProductSku(**fields)
    db.add(sku)
    db.flush()
    return sku


def _upsert_company_and_facility(db) -> Facility:
    """MVP tek kiracılı: tek Company + tek Facility. Firma Gerçek Veri
    Kütüphanesi'ndeki her varlık (makine, hammadde, reçete...) buraya bağlanır."""
    company = db.query(Company).filter_by(name="Demo Ambalaj San. A.Ş.").one_or_none()
    if company is None:
        company = Company(name="Demo Ambalaj San. A.Ş.")
        db.add(company)
        db.flush()
    facility = db.query(Facility).filter_by(company_id=company.id, name="Merkez Tesis").one_or_none()
    if facility is None:
        facility = Facility(company_id=company.id, name="Merkez Tesis", address="OSB, Türkiye")
        db.add(facility)
        db.flush()
    return facility


def _upsert_cost_factor(db, facility_id: str, **fields) -> CostFactor:
    """Tesis başına tek 'aktif' maliyet kaydı — gerçek fatura/sözleşme
    verisi bağlanana kadar `is_demo_placeholder=True` ile açıkça işaretli
    VARSAYIMSAL rakamlar (bkz. app/models/cost.py'deki carbon EF ile aynı
    ilke: demo veri asla gerçekmiş gibi sunulmaz)."""
    existing = db.query(CostFactor).filter_by(facility_id=facility_id).one_or_none()
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        db.flush()
        return existing
    cf = CostFactor(facility_id=facility_id, **fields)
    db.add(cf)
    db.flush()
    return cf


def _upsert_line(db, **fields) -> ProductionLine:
    existing = db.query(ProductionLine).filter_by(name=fields["name"]).one_or_none()
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        db.flush()
        return existing
    line = ProductionLine(**fields)
    db.add(line)
    db.flush()
    return line


def _set_compat(db, line: ProductionLine, material_id: str, max_ratio_pct: float) -> None:
    existing = (
        db.query(LineMaterialCompatibility)
        .filter_by(line_id=line.id, material_id=material_id)
        .one_or_none()
    )
    if existing:
        existing.max_ratio_pct = max_ratio_pct
        return
    db.add(
        LineMaterialCompatibility(line_id=line.id, material_id=material_id, max_ratio_pct=max_ratio_pct)
    )


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ids = load_all(db)
        material_ids = ids["materials"]

        facility = _upsert_company_and_facility(db)

        _upsert_cost_factor(
            db,
            facility_id=facility.id,
            currency="TRY",
            electricity_rate=3.2,
            gas_rate=18.5,
            labor_rate=180.0,
            waste_disposal_cost=4.5,
            recovery_cost=2.0,
            machine_hour_rate=650.0,
            is_demo_placeholder=True,
            source="DEMO/VARSAYIMSAL — gerçek fatura/sözleşme verisi bağlanmadı",
        )

        line1 = _upsert_line(
            db,
            facility_id=facility.id,
            name="Hat-1 - Termoform Tabak Hattı",
            process_type="Thermoforming",
            extruder_count=2,
            layer_structure="A/B/A",
            layer_count=3,
            min_micron=300,
            max_micron=900,
            min_gsm=None,
            max_gsm=None,
            max_width_mm=800,
            min_dosage_pct=0,
            max_dosage_pct=50,
            line_speed_m_min=25,
            supported_packaging_types=["plastik_tabak"],
            energy_kwh_per_kg=0.45,
            active=True,
        )
        line2 = _upsert_line(
            db,
            facility_id=facility.id,
            name="Hat-2 - Esnek Film Ekstrüzyon Hattı",
            process_type="Blown Film Extrusion",
            extruder_count=2,
            layer_structure="A/B/A",
            layer_count=3,
            min_micron=20,
            max_micron=120,
            min_gsm=None,
            max_gsm=None,
            max_width_mm=1500,
            min_dosage_pct=0,
            max_dosage_pct=50,
            line_speed_m_min=150,
            supported_packaging_types=["esnek_film_ambalaj"],
            energy_kwh_per_kg=0.30,
            active=True,
        )
        line3 = _upsert_line(
            db,
            facility_id=facility.id,
            name="Hat-3 - Şişe Üfleme Hattı",
            process_type="Blow Molding",
            extruder_count=1,
            layer_structure="A",
            layer_count=1,
            min_micron=200,
            max_micron=600,
            min_gsm=None,
            max_gsm=None,
            max_width_mm=None,
            min_dosage_pct=0,
            max_dosage_pct=70,
            line_speed_m_min=60,
            supported_packaging_types=["sise"],
            energy_kwh_per_kg=0.50,
            active=True,
        )
        line4 = _upsert_line(
            db,
            facility_id=facility.id,
            name="Hat-4 - Kapak Enjeksiyon Hattı",
            process_type="Injection Molding",
            extruder_count=1,
            layer_structure="A",
            layer_count=1,
            min_micron=800,
            max_micron=2500,
            min_gsm=None,
            max_gsm=None,
            max_width_mm=None,
            min_dosage_pct=0,
            max_dosage_pct=50,
            line_speed_m_min=40,
            supported_packaging_types=["kapak"],
            energy_kwh_per_kg=0.40,
            active=True,
        )
        line5 = _upsert_line(
            db,
            facility_id=facility.id,
            name="Hat-5 - Bardak/Kap Termoform Hattı",
            process_type="Thermoforming",
            extruder_count=2,
            layer_structure="A/B/A",
            layer_count=3,
            min_micron=250,
            max_micron=700,
            min_gsm=None,
            max_gsm=None,
            max_width_mm=800,
            min_dosage_pct=0,
            max_dosage_pct=50,
            line_speed_m_min=30,
            supported_packaging_types=["plastik_bardak", "plastik_kap"],
            energy_kwh_per_kg=0.40,
            active=True,
        )
        db.flush()

        tabak_materials = [
            ("PP Virgin Enjeksiyon Sınıfı", 100),
            ("PP PCR Gıda Sınıfı (Dekontaminasyonlu)", 50),
            ("PP Regranül (Post-Endüstriyel)", 30),
            ("PET Virgin Şişe/Tabak Sınıfı", 100),
            ("rPET Gıda Sınıfı (Dekontaminasyonlu)", 70),
            ("PET Regranül (Endüstriyel)", 20),
            ("PS Virgin", 100),
            ("PS Regranül (Post-Endüstriyel)", 20),
        ]
        for name, ratio in tabak_materials:
            _set_compat(db, line1, material_ids[name], ratio)

        film_materials = [
            ("PE Virgin Film Sınıfı", 100),
            ("PE PCR Post-Tüketici (Sertifikasız)", 40),
            ("PE Regranül (Dahili Fire Geri Kazanım)", 25),
            ("PP Virgin Enjeksiyon Sınıfı", 100),
            ("PP PCR Gıda Sınıfı (Dekontaminasyonlu)", 50),
        ]
        for name, ratio in film_materials:
            _set_compat(db, line2, material_ids[name], ratio)

        sise_materials = [
            ("PET Virgin Şişe/Tabak Sınıfı", 100),
            ("rPET Gıda Sınıfı (Dekontaminasyonlu)", 70),
            ("PET Regranül (Endüstriyel)", 20),
        ]
        for name, ratio in sise_materials:
            _set_compat(db, line3, material_ids[name], ratio)

        kapak_materials = [
            ("PP Virgin Enjeksiyon Sınıfı", 100),
            ("PP PCR Gıda Sınıfı (Dekontaminasyonlu)", 50),
            ("PP Regranül (Post-Endüstriyel)", 30),
        ]
        for name, ratio in kapak_materials:
            _set_compat(db, line4, material_ids[name], ratio)

        for name, ratio in tabak_materials:  # bardak/kap için de aynı hammadde havuzu geçerli
            _set_compat(db, line5, material_ids[name], ratio)

        db.commit()

        # --- Faz B.5: tek bir demo SKU (Ürün/SKU Kütüphanesi) — tabak talebini
        # kalıcı bir ürün kimliğine bağlar. Bu talep Aşama 12'de doğrulandığında
        # sku.current_recipe_id otomatik güncellenecek (bkz. production_flow_
        # service.finalize_result) ve gelecekteki aynı SKU'ya yönelik talepler
        # onu salt metin eşleşmesinden daha kesin bir referans olarak bulacak.
        tabak_sku = _upsert_product_sku(
            db,
            sku_code="TBK-001",
            product_name="Tek Kullanımlık Yemek Tabağı 230x230",
            packaging_type="plastik tabak",
            usage_area="gıda servisi (yemek tabağı)",
            target_market="AB",
            food_contact=True,
            dimensions={"length_mm": 230, "width_mm": 230, "height_mm": 20},
            layer_count=3,
            layer_structure="A/B/A",
        )
        db.commit()

        # --- Demo ambalaj talepleri: uçtan uca 3-7. aşamaları çalıştır -------
        demo_requests = [
            {
                "packaging_type": "plastik tabak",
                "usage_area": "gıda servisi (yemek tabağı)",
                "product": "tek kullanımlık yemek tabağı",
                "target_market": "AB",
                "food_contact": True,
                "target_volume_units": 500_000,
                "dimensions": {"length_mm": 230, "width_mm": 230, "height_mm": 20},
                "sku_id": tabak_sku.id,
            },
            {
                "packaging_type": "PET şişe",
                "usage_area": "içecek ambalajı",
                "product": "500ml içecek şişesi",
                "target_market": "AB",
                "food_contact": True,
                "target_volume_units": 1_000_000,
                "dimensions": {"length_mm": 220, "width_mm": 65, "height_mm": 65},
            },
            {
                "packaging_type": "şişe kapağı",
                "usage_area": "içecek ambalajı",
                "product": "vidalı şişe kapağı",
                "target_market": "AB",
                "food_contact": True,
                "target_volume_units": 1_000_000,
                "dimensions": {"length_mm": 30, "width_mm": 30, "height_mm": 15},
            },
            {
                "packaging_type": "esnek film ambalaj",
                "usage_area": "kuru gıda poşetleme",
                "product": "atıştırmalık poşeti",
                "target_market": "yurt içi",
                "food_contact": True,
                "target_volume_units": 300_000,
                "dimensions": {"length_mm": 180, "width_mm": 120, "height_mm": None},
            },
        ]

        for payload in demo_requests:
            req = packaging_service.create_packaging_request(db, payload)
            print(f"\n=== Ambalaj Talebi: '{payload['packaging_type']}' ===")

            overall, assessments = packaging_service.assess_regulations(db, req)
            print(f"[Aşama 3] Mevzuat sonucu: {overall} ({len(assessments)} madde değerlendirildi)")

            matches = packaging_service.match_infrastructure(db, req)
            print(f"[Aşama 4] {len(matches)} uygun hat bulundu: {[m['line'].name for m in matches]}")
            if not matches:
                print("  (Uygun hat yok — bu talep atlanıyor)")
                continue

            line = matches[0]["line"]
            initial_recipe = packaging_service.generate_initial_recipe(db, req, line)
            print(f"[Aşama 5] Başlangıç reçetesi oluşturuldu: {initial_recipe.id} (kaynak={initial_recipe.source})")

            result = optimization_service.run_optimization(db, req.id, line.id, ratio_step_pct=10)
            print(
                f"[Aşama 6-7] {result['generated_candidate_count']} aday üretildi, "
                f"{result['survived_constraint_engine_count']} tanesi kısıt motorundan geçti, "
                f"{len(result['finalist_candidate_ids'])} finalist sunuldu, "
                f"{len(result['notable_eliminated'])} elenen örnek gösteriliyor."
            )
            print(f"Ambalaj talebi ID: {req.id} · Hat ID: {line.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
