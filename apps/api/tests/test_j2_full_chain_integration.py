"""Faz J.2 — Madde 24: Nihai Sistem Bağlantı Zinciri Doğrulaması.

Firma Profili -> Tesis -> Makine Parkı -> Hammadde Kütüphanesi -> Ürün/SKU
Hafızası -> Yeni Ambalaj Tanımlama -> Mevzuat Ön Değerlendirmesi -> Gerçek
Altyapı Eşleştirmesi -> Akıllı Başlangıç -> Dinamik Aday Üretimi + Kısıt
Taraması + Çok Kriterli Optimizasyon -> Reçete Önerileri + Tahmini
Karşılaştırma -> Üretim Emri -> Gerçek/Simülasyon Üretim Takibi -> Fiziksel
Doğrulama -> Gerçekleşen Sonuç -> Firma Öğrenme Hafızası -> Optimizasyon
Raporu -> Dijital Ürün Pasaportu.

TEK bir sürekli akışta, GERÇEK HTTP çağrılarıyla (mock DEĞİL) uçtan uca
ilerletilir; her adımda bir önceki adımın GERÇEK id/verisinin kullanıldığı
assert edilir -- rastgele/kopuk veri sızarsa test kırılır."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.knowledge_base.loader import load_regulations
from app.models.infrastructure import LineMaterialCompatibility
from app.models.knowledge import Polymer


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_j2_full_chain_from_company_profile_to_dpp(client, db_session):
    load_regulations(db_session)

    # 1) Firma Profili
    company_resp = client.post(
        "/api/v1/company/profile",
        json={"name": "J2 Test Ambalaj San. A.Ş.", "country": "Türkiye", "city": "İstanbul"},
    )
    assert company_resp.status_code == 200, company_resp.text
    company = company_resp.json()["company"]
    assert company["name"] == "J2 Test Ambalaj San. A.Ş."

    # 2) Tesis
    facility_resp = client.post(
        "/api/v1/company/facilities",
        json={"name": "J2 Test Tesis - Gebze"},
    )
    assert facility_resp.status_code == 200, facility_resp.text
    facility = facility_resp.json()
    assert facility["company_id"] == company["id"], "Tesis, GERÇEKTEN 1. adımda kurulan firmaya bağlı olmalı"

    # 3) Makine Parkı
    line_resp = client.post(
        "/api/v1/production-lines",
        json={
            "facility_id": facility["id"], "name": "J2 Test Hat - Esnek Film",
            "process_type": "Blown Film Extrusion", "layer_structure": "A", "layer_count": 1,
            "min_micron": 20.0, "max_micron": 200.0, "line_speed_m_min": 60.0,
            "supported_packaging_types": ["esnek_film_ambalaj"],
        },
    )
    assert line_resp.status_code == 200, line_resp.text
    line = line_resp.json()
    assert line["facility_id"] == facility["id"], "Hat, GERÇEKTEN 2. adımda kurulan tesise bağlı olmalı"

    # 4) Hammadde Kütüphanesi (Polymer, HTTP endpoint'i yok -- sistem
    # referans verisi, doğrudan seed edilir; Material'ler GERÇEK HTTP ile)
    # Faz K.6 -- kod GERÇEKTEN "esnek film ambalaj"ın tercih ettiği listedeki
    # ("PE") bir polimerle eşleşmeli; artık uyumsuz bir kod (eski "J2-PE")
    # generate_initial_recipe'in Akıllı Başlangıç adımında sessizce herhangi
    # bir virgin malzemeye düşmüyor, açık bir ValueError fırlatıyor.
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.commit()
    db_session.refresh(polymer)

    virgin_resp = client.post(
        "/api/v1/materials",
        json={
            "polymer_id": polymer.id, "name": "J2 PE Virgin Film Sınıfı", "material_type": "virgin",
            "density_g_cm3": 0.92, "food_contact_eligible": True, "max_recommended_ratio_pct": 100.0,
            "cost_per_kg": 30.0, "carbon_factor_kg_co2_per_kg": 1.8,
        },
    )
    assert virgin_resp.status_code == 200, virgin_resp.text
    virgin = virgin_resp.json()
    assert virgin["polymer_id"] == polymer.id

    pcr_resp = client.post(
        "/api/v1/materials",
        json={
            "polymer_id": polymer.id, "name": "J2 PE PCR Gıda Sınıfı", "material_type": "pcr",
            "density_g_cm3": 0.92, "degradation_factor": 0.08, "food_contact_eligible": True,
            "max_recommended_ratio_pct": 50.0, "cost_per_kg": 26.0, "carbon_factor_kg_co2_per_kg": 0.6,
        },
    )
    assert pcr_resp.status_code == 200, pcr_resp.text
    pcr = pcr_resp.json()

    # Hat-malzeme uyumu (HTTP endpoint'i yok -- Faz E.2/machine_park.py bunu
    # dışa açmıyor, doğrudan seed edilir).
    db_session.add(LineMaterialCompatibility(line_id=line["id"], material_id=virgin["id"], max_ratio_pct=100.0))
    db_session.add(LineMaterialCompatibility(line_id=line["id"], material_id=pcr["id"], max_ratio_pct=50.0))
    db_session.commit()

    # 5) Ürün/SKU Hafızası
    sku_resp = client.post(
        "/api/v1/product-skus",
        json={
            "sku_code": "J2-SKU-001", "product_name": "J2 Atıştırmalık Poşeti", "packaging_type": "esnek film ambalaj",
            "usage_area": "kuru gıda poşetleme", "target_market": "AB", "food_contact": True,
            "line_id": line["id"],
        },
    )
    assert sku_resp.status_code == 200, sku_resp.text
    sku = sku_resp.json()
    assert sku["line_id"] == line["id"], "SKU, GERÇEKTEN 3. adımda kurulan hatla ilişkilendirilmiş olmalı"

    # 6) Yeni Ambalaj Tanımlama (SKU'ya bağlı)
    req_resp = client.post(
        "/api/v1/packaging-flow/requests",
        json={
            "packaging_type": "esnek film ambalaj", "usage_area": "kuru gıda poşetleme",
            "product": "J2 Atıştırmalık Poşeti", "target_market": "AB", "food_contact": True,
            "target_volume_units": 2000, "dimensions": {"length_mm": 300, "width_mm": 200},
            "sku_id": sku["id"],
        },
    )
    assert req_resp.status_code == 200, req_resp.text
    req = req_resp.json()
    assert req["sku_id"] == sku["id"], "Ambalaj talebi, GERÇEKTEN 5. adımda kurulan SKU'ya bağlı olmalı"

    # 7) Mevzuat Ön Değerlendirmesi
    reg_resp = client.post(f"/api/v1/packaging-flow/requests/{req['id']}/regulatory-assessment")
    assert reg_resp.status_code == 200, reg_resp.text
    reg_data = reg_resp.json()
    assert len(reg_data["assessments"]) > 0, "food_contact=True bir talep için en az bir madde değerlendirilmeli"

    # 8) Gerçek Altyapı Eşleştirmesi
    matches_resp = client.get(f"/api/v1/packaging-flow/requests/{req['id']}/infrastructure-matches")
    assert matches_resp.status_code == 200, matches_resp.text
    matched_line_ids = {m["line"]["id"] for m in matches_resp.json()}
    assert line["id"] in matched_line_ids, "3. adımda kurulan GERÇEK hat eşleştirme sonuçlarında görünmeli"

    # 9) Akıllı Başlangıç
    initial_resp = client.post(
        f"/api/v1/packaging-flow/requests/{req['id']}/initial-recipe", params={"line_id": line["id"]}
    )
    assert initial_resp.status_code == 200, initial_resp.text
    seed_recipe = initial_resp.json()
    assert seed_recipe["packaging_request_id"] == req["id"]
    assert seed_recipe["line_id"] == line["id"]

    # 10) Dinamik Aday Üretimi + Kısıt Taraması + Çok Kriterli Optimizasyon
    run_resp = client.post(
        f"/api/v1/optimization/requests/{req['id']}/run", params={"line_id": line["id"], "ratio_step_pct": 10}
    )
    assert run_resp.status_code == 200, run_resp.text
    run = run_resp.json()
    assert len(run["finalists"]) > 0, "Gerçek malzeme/hat kurulumu en az bir finalist üretmeli"
    finalist = run["finalists"][0]
    finalist_material_ids = {layer["material_id"] for layer in finalist["recipe"]["layers"]}
    assert finalist_material_ids.issubset({virgin["id"], pcr["id"]}), (
        "Finalist katmanları SADECE 4. adımda kurulan GERÇEK malzemeleri kullanmalı"
    )
    recipe_id = finalist["recipe"]["id"]

    # 11) Reçete Önerileri + Tahmini Karşılaştırma (Aşama 8)
    comparison_resp = client.get(f"/api/v1/production-flow/recipes/{recipe_id}/comparison")
    assert comparison_resp.status_code == 200, comparison_resp.text
    comparison = comparison_resp.json()
    assert comparison["recommended"]["is_estimated"] is True

    # 12) Üretim Emri
    order_resp = client.post(
        f"/api/v1/production-flow/recipes/{recipe_id}/production-orders",
        params={"qty_units": 2000, "approved_by": "J2 Test Operatörü"},
    )
    assert order_resp.status_code == 200, order_resp.text
    order = order_resp.json()
    assert order["recipe_id"] == recipe_id
    assert order["line_id"] == line["id"], "Üretim emri, GERÇEKTEN 3. adımın hattına bağlı olmalı"

    # 13) Gerçek/Simülasyon Üretim Takibi
    live_resp = client.post(f"/api/v1/production-flow/production-orders/{order['id']}/simulate-live-data")
    assert live_resp.status_code == 200, live_resp.text
    assert len(live_resp.json()) > 0

    # 14) Fiziksel Doğrulama (geçen değerlerle -- düz akış)
    thickness = finalist["recipe"]["total_micron"] or 70.0
    verify_resp = client.post(
        "/api/v1/production-flow/physical-verification",
        json={"production_order_id": order["id"], "tests": [
            {"test_type": "kalinlik", "value": thickness, "unit": "mikron", "target_min": thickness * 0.9, "target_max": thickness * 1.1, "test_method": "ISO 4593"},
        ]},
    )
    assert verify_resp.status_code == 200, verify_resp.text
    assert verify_resp.json()["all_passed"] is True

    # 15) Gerçekleşen Sonuç
    finalize_resp = client.post(f"/api/v1/production-flow/recipes/{recipe_id}/finalize")
    assert finalize_resp.status_code == 200, finalize_resp.text
    final_result = finalize_resp.json()
    assert final_result["recipe_id"] == recipe_id
    assert final_result["physical_tests_passed"] is True

    # 16) Firma Öğrenme Hafızası
    chain_resp = client.get(f"/api/v1/production-flow/recipes/{recipe_id}/causal-chain")
    assert chain_resp.status_code == 200, chain_resp.text
    chain = chain_resp.json()
    assert len(chain) == 1  # tek halka, hiç revizyon yok
    assert chain[0]["id"] == recipe_id
    assert chain[0]["line_name"] == line["name"], "Zincir, GERÇEKTEN 3. adımın hattını yansıtmalı"

    # 17) Optimizasyon Raporu
    report_resp = client.get(f"/api/v1/production-flow/recipes/{recipe_id}/optimization-report")
    assert report_resp.status_code == 200, report_resp.text
    assert report_resp.content[:5] == b"%PDF-"

    # 18) Dijital Ürün Pasaportu
    passport_resp = client.post("/api/v1/passports", json={"recipe_id": recipe_id})
    assert passport_resp.status_code == 200, passport_resp.text
    passport = passport_resp.json()
    header = passport["public"]["header"]
    assert header["recipe_id"] == recipe_id
    assert header["company_name"] == company["name"], "DPP, GERÇEKTEN 1. adımın firma adını göstermeli"
    assert header["facility_name"] == facility["name"], "DPP, GERÇEKTEN 2. adımın tesis adını göstermeli"
    assert header["line_name"] == line["name"], "DPP, GERÇEKTEN 3. adımın hat adını göstermeli"
    assert header["sku_code"] == sku["sku_code"], "DPP, GERÇEKTEN 5. adımın SKU kodunu göstermeli"
