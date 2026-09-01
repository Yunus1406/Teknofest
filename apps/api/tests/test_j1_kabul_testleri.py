"""Faz J.1 — 10 Kritik Kabul Testi (orijinal dokümandan birebir). Her test
gerçek dev-benzeri bir DB üzerinde (`db_session`), akış adımları GERÇEK HTTP
çağrılarıyla (`TestClient`, mock DEĞİL) çalıştırılır. Sadece temel referans
veri (Polymer/Material/ProductionLine) mevcut codebase konvansiyonuyla
doğrudan `db_session`'a seed edilir -- bunun için zaten bir HTTP endpoint'i
yok (Polymer sistem referans verisi, Material/ProductionLine ise Faz E'nin
HTTP endpoint'leri üzerinden de kurulabilir ama testte doğrudan seed etmek
mevcut TÜM diğer test dosyalarının deseniyle birebir aynı)."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine
from app.models.knowledge import CarbonEmissionFactor, Material, Polymer
from app.models.optimization import OptimizationCandidate
from app.models.recipe import Recipe
from app.services.production_flow_service import version_history


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _seed_materials(db):
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    virgin = Material(
        polymer_id=polymer.id, name="PE Virgin Film Sınıfı", material_type="virgin", density_g_cm3=0.92,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    pcr = Material(
        polymer_id=polymer.id, name="PE PCR Gıda Sınıfı", material_type="pcr", density_g_cm3=0.92,
        degradation_factor=0.08, food_contact_eligible=True, max_recommended_ratio_pct=50.0,
        cost_per_kg=26.0, carbon_factor_kg_co2_per_kg=0.6,
    )
    db.add_all([virgin, pcr])
    db.flush()
    return polymer, virgin, pcr


def _seed_line(
    db, virgin, pcr, name="Test Hat", pcr_max_ratio=50.0, min_micron=20.0, max_micron=200.0,
    line_speed=50.0, layer_structure="A", layer_count=1,
):
    line = ProductionLine(
        name=name, process_type="Blown Film Extrusion", layer_structure=layer_structure, layer_count=layer_count,
        min_micron=min_micron, max_micron=max_micron, line_speed_m_min=line_speed,
        supported_packaging_types=["esnek_film_ambalaj"], active=True,
    )
    db.add(line)
    db.flush()
    db.add(LineMaterialCompatibility(line_id=line.id, material_id=virgin.id, max_ratio_pct=100.0))
    if pcr_max_ratio is not None:
        db.add(LineMaterialCompatibility(line_id=line.id, material_id=pcr.id, max_ratio_pct=pcr_max_ratio))
    db.commit()
    db.refresh(line)
    return line


def _create_request(client, food_contact=True, dims=None):
    resp = client.post(
        "/api/v1/packaging-flow/requests",
        json={
            "packaging_type": "esnek film ambalaj", "usage_area": "kuru gıda poşetleme",
            "product": "atıştırmalık poşeti", "target_market": "AB", "food_contact": food_contact,
            "target_volume_units": 1000, "dimensions": dims or {"length_mm": 300, "width_mm": 200},
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- Test 1: Dinamik optimizasyon ------------------------------------------

def test_1_pcr_limit_degisince_aday_sayisi_degisir(client, db_session):
    _, virgin, pcr = _seed_materials(db_session)
    line = _seed_line(db_session, virgin, pcr, pcr_max_ratio=10.0)
    req = _create_request(client)

    run1 = client.post(f"/api/v1/optimization/requests/{req['id']}/run", params={"line_id": line.id, "ratio_step_pct": 10})
    assert run1.status_code == 200, run1.text
    count1 = run1.json()["generated_candidate_count"]

    # PCR sınırını genişlet -- gerçek lever: LineMaterialCompatibility.max_ratio_pct
    compat = (
        db_session.query(LineMaterialCompatibility)
        .filter_by(line_id=line.id, material_id=pcr.id)
        .one()
    )
    compat.max_ratio_pct = 50.0
    db_session.commit()

    req2 = _create_request(client)
    run2 = client.post(f"/api/v1/optimization/requests/{req2['id']}/run", params={"line_id": line.id, "ratio_step_pct": 10})
    assert run2.status_code == 200, run2.text
    count2 = run2.json()["generated_candidate_count"]

    assert count2 > count1, f"PCR sınırı genişleyince aday sayısı artmalı: {count1} -> {count2}"


# --- Test 2: Makine değişimi -------------------------------------------------

def test_2_farkli_hat_farkli_aday_havuzu_uretir(client, db_session):
    """Farklı kapasite/katman yapısına sahip bir hat seçildiğinde aday
    havuzu GERÇEKTEN değişmeli. Gerçek lever: `ProductionLine.layer_count`/
    `layer_structure` -- referans reçetesi olmayan bir talep için katman
    sayısı DOĞRUDAN hattan türetilir (mikron aralığı ise kasıtlı olarak
    hattan uyumlu üretildiği için tek başına ayırt edici değil, deneysel
    olarak doğrulandı: aynı mikron aralığı farkı survived sayısını
    değiştirmiyor)."""
    _, virgin, pcr = _seed_materials(db_session)
    line_a = _seed_line(db_session, virgin, pcr, name="Hat A - Tek Katman", layer_structure="A", layer_count=1)
    line_b = _seed_line(db_session, virgin, pcr, name="Hat B - Üç Katman Farklı Kapasite", layer_structure="A/B/A", layer_count=3, line_speed=120.0)
    req_a = _create_request(client)
    req_b = _create_request(client)

    run_a = client.post(f"/api/v1/optimization/requests/{req_a['id']}/run", params={"line_id": line_a.id, "ratio_step_pct": 10})
    run_b = client.post(f"/api/v1/optimization/requests/{req_b['id']}/run", params={"line_id": line_b.id, "ratio_step_pct": 10})
    assert run_a.status_code == 200, run_a.text
    assert run_b.status_code == 200, run_b.text

    generated_a = run_a.json()["generated_candidate_count"]
    generated_b = run_b.json()["generated_candidate_count"]
    assert generated_a != generated_b, f"İki farklı hat aynı aday sayısını üretmemeli: {generated_a} == {generated_b}"

    finalist_layer_count_a = len({l["layer_index"] for l in run_a.json()["finalists"][0]["recipe"]["layers"]})
    finalist_layer_count_b = len({l["layer_index"] for l in run_b.json()["finalists"][0]["recipe"]["layers"]})
    assert finalist_layer_count_a == 1
    assert finalist_layer_count_b == 3


# --- Test 3: Hammadde değişimi ----------------------------------------------

def test_3_pcr_hammaddesi_kaldirilinca_pcr_iceren_aday_olusmaz(client, db_session):
    _, virgin, pcr = _seed_materials(db_session)
    line = _seed_line(db_session, virgin, pcr, pcr_max_ratio=50.0)
    # PCR hammaddesini hattan tamamen kaldır (uyumluluk satırını sil).
    db_session.query(LineMaterialCompatibility).filter_by(line_id=line.id, material_id=pcr.id).delete()
    db_session.commit()

    req = _create_request(client)
    run = client.post(f"/api/v1/optimization/requests/{req['id']}/run", params={"line_id": line.id, "ratio_step_pct": 10})
    assert run.status_code == 200, run.text
    data = run.json()

    for finalist in data["finalists"]:
        for layer in finalist["recipe"]["layers"]:
            assert layer["material_id"] != pcr.id, "PCR hammaddesi kaldırıldıktan sonra hiçbir finalist PCR içermemeli"
    for eliminated in data["notable_eliminated"]:
        assert "PCR" not in eliminated["composition_summary"] or "%0 PCR" in eliminated["composition_summary"]


# --- Test 4: Mevzuat ---------------------------------------------------------

def test_4_gida_temasi_degisince_uygulanan_maddeler_degisir(client, db_session):
    from app.knowledge_base.loader import load_regulations

    _seed_materials(db_session)
    load_regulations(db_session)
    req_yes = _create_request(client, food_contact=True)
    req_no = _create_request(client, food_contact=False)

    resp_yes = client.post(f"/api/v1/packaging-flow/requests/{req_yes['id']}/regulatory-assessment")
    resp_no = client.post(f"/api/v1/packaging-flow/requests/{req_no['id']}/regulatory-assessment")
    assert resp_yes.status_code == 200, resp_yes.text
    assert resp_no.status_code == 200, resp_no.text

    codes_yes = {a["regulation_id"] for a in resp_yes.json()["assessments"]}
    codes_no = {a["regulation_id"] for a in resp_no.json()["assessments"]}
    # PPWR-ART-5 (PFAS) SADECE gıda temaslı ambalajlarda uygulanır (bkz.
    # packaging_service.py run_regulatory_assessment) -- iki set FARKLI olmalı.
    assert codes_yes != codes_no, "food_contact True/False aynı mevzuat setini üretmemeli"
    assert len(codes_yes) > len(codes_no), "Gıda temaslı ambalaj en az bir ek madde (PFAS) taşımalı"


# --- Test 5: Fiziksel doğrulama (eksik test) --------------------------------

def _seed_verified_line_recipe(db, virgin, pcr):
    line = _seed_line(db, virgin, pcr, name="Test Hat Fiziksel")
    from app.models.recipe import PackagingRequest, RecipeLayer

    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="test", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 300, "width_mm": 200},
    )
    db.add(req)
    db.flush()
    recipe = Recipe(packaging_request_id=req.id, version=1, source="sistem_uretti", status="onerildi", total_micron=70.0, line_id=line.id)
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=virgin.id, ratio_pct=100.0, thickness_micron=70.0))
    db.commit()
    db.refresh(recipe)
    return line, recipe


def test_5_tensile_girilmezse_gecti_sonucu_olusmaz(client, db_session):
    _, virgin, pcr = _seed_materials(db_session)
    line, recipe = _seed_verified_line_recipe(db_session, virgin, pcr)

    order_resp = client.post(
        f"/api/v1/production-flow/recipes/{recipe.id}/production-orders",
        params={"qty_units": 1000, "approved_by": "Test Operatör"},
    )
    assert order_resp.status_code == 200, order_resp.text
    order_id = order_resp.json()["id"]

    verify_resp = client.post(
        "/api/v1/production-flow/physical-verification",
        json={"production_order_id": order_id, "tests": [
            {"test_type": "kalinlik", "value": 70.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None},
        ]},
    )
    assert verify_resp.status_code == 200, verify_resp.text
    results = verify_resp.json()["results"]
    test_types = {r["test_type"] for r in results}
    assert "tensile" not in test_types, "Girilmemiş bir test ASLA sonuç listesinde 'Geçti' olarak belirmemeli"


# --- Test 6: Başarısız fiziksel test -> V1 -> V2 ----------------------------

def test_6_basarisiz_test_yeni_versiyon_olusturur(client, db_session):
    _, virgin, pcr = _seed_materials(db_session)
    line, recipe = _seed_verified_line_recipe(db_session, virgin, pcr)

    order_resp = client.post(
        f"/api/v1/production-flow/recipes/{recipe.id}/production-orders",
        params={"qty_units": 1000, "approved_by": "Test Operatör"},
    )
    order_id = order_resp.json()["id"]

    verify_resp = client.post(
        "/api/v1/production-flow/physical-verification",
        json={"production_order_id": order_id, "tests": [
            {"test_type": "kalinlik", "value": 40.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": "ISO 4593"},
        ]},
    )
    assert verify_resp.status_code == 200, verify_resp.text
    data = verify_resp.json()
    assert data["all_passed"] is False
    assert data["new_recipe_version"] is not None
    v2 = data["new_recipe_version"]
    assert v2["version"] == 2
    assert v2["parent_recipe_id"] == recipe.id

    db_session.refresh(recipe)
    assert recipe.status == "revizyon_gerekli"
    assert recipe.is_verified is False


# --- Test 7: Firma hafızası V2'yi bulmalı -----------------------------------

def test_7_firma_hafizasi_dogrulanmis_v2yi_bulur(client, db_session):
    _, virgin, pcr = _seed_materials(db_session)
    line, recipe = _seed_verified_line_recipe(db_session, virgin, pcr)

    order1 = client.post(
        f"/api/v1/production-flow/recipes/{recipe.id}/production-orders",
        params={"qty_units": 1000, "approved_by": "Test Operatör"},
    ).json()
    verify1 = client.post(
        "/api/v1/production-flow/physical-verification",
        json={"production_order_id": order1["id"], "tests": [
            {"test_type": "kalinlik", "value": 40.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None},
        ]},
    ).json()
    v2_id = verify1["new_recipe_version"]["id"]

    # V2 için gerçek üretim + GEÇEN test -> gerçekten doğrulanmış olsun.
    v2 = db_session.get(Recipe, v2_id)
    v2.line_id = line.id
    db_session.commit()
    order2 = client.post(
        f"/api/v1/production-flow/recipes/{v2_id}/production-orders",
        params={"qty_units": 1000, "approved_by": "Test Operatör"},
    ).json()
    client.post(f"/api/v1/production-flow/production-orders/{order2['id']}/simulate-live-data")
    verify2 = client.post(
        "/api/v1/production-flow/physical-verification",
        json={"production_order_id": order2["id"], "tests": [
            {"test_type": "kalinlik", "value": 70.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None},
        ]},
    )
    assert verify2.json()["all_passed"] is True
    finalize = client.post(f"/api/v1/production-flow/recipes/{v2_id}/finalize")
    assert finalize.status_code == 200, finalize.text

    # AYNI özelliklerde YENİ bir ambalaj talebi -- Akıllı Başlangıç V2'yi bulmalı.
    new_req = _create_request(client)
    initial = client.post(
        f"/api/v1/packaging-flow/requests/{new_req['id']}/initial-recipe", params={"line_id": line.id}
    )
    assert initial.status_code == 200, initial.text
    evidence = initial.json()["reference_search_evidence"]
    assert evidence is not None, "Firma hafızası doğrulanmış V2'yi bulmalı, boş dönmemeli"
    assert v2_id in evidence["candidate_recipe_ids"]
    assert recipe.id not in evidence["candidate_recipe_ids"], "V1 hiç doğrulanmadı, kanıt olarak kullanılmamalı"


# --- Test 8: Rapor tutarlılığı (ekran vs PDF) -------------------------------

def test_8_ekran_ve_pdf_degerleri_birebir_ayni(client, db_session):
    _, virgin, pcr = _seed_materials(db_session)
    line, recipe = _seed_verified_line_recipe(db_session, virgin, pcr)

    order = client.post(
        f"/api/v1/production-flow/recipes/{recipe.id}/production-orders",
        params={"qty_units": 1000, "approved_by": "Test Operatör"},
    ).json()
    client.post(f"/api/v1/production-flow/production-orders/{order['id']}/simulate-live-data")
    client.post(
        "/api/v1/production-flow/physical-verification",
        json={"production_order_id": order["id"], "tests": [
            {"test_type": "kalinlik", "value": 70.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None},
        ]},
    )
    finalize_resp = client.post(f"/api/v1/production-flow/recipes/{recipe.id}/finalize")
    assert finalize_resp.status_code == 200, finalize_resp.text
    screen_per_1000 = finalize_resp.json()["per_1000_units"]  # "ekranın" okuduğu GERÇEK JSON

    pdf_resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/optimization-report")
    assert pdf_resp.status_code == 200, pdf_resp.text
    assert pdf_resp.content[:5] == b"%PDF-"

    from io import BytesIO
    from pypdf import PdfReader
    pdf_text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(pdf_resp.content)).pages)

    checked_any = False
    for key in ("virgin_kg", "pcr_kg", "karbon_kg_co2"):
        value = screen_per_1000.get(key)
        if isinstance(value, (int, float)):
            checked_any = True
            formatted = f"{value:.2f}" if key != "virgin_kg" else f"{value:.2f}"
            assert formatted in pdf_text, f"Ekrandaki {key}={formatted} PDF metninde bulunamadı"
    assert checked_any, "Karşılaştırılacak en az bir gerçek sayısal değer olmalı"


# --- Test 9: Kaynak değişimi -------------------------------------------------

def test_9_karbon_kaynagi_degisince_hesap_ve_rapor_guncellenir(client, db_session):
    _, virgin, pcr = _seed_materials(db_session)
    line, recipe = _seed_verified_line_recipe(db_session, virgin, pcr)

    ef_old = CarbonEmissionFactor(
        material_key="PE Virgin ESKİ", factor_type="malzeme", ef_value=1.8, unit="kg_co2e_per_kg",
        source="Kaynak A - eski", year=2023, version="1.0", is_demo_placeholder=True,
    )
    db_session.add(ef_old)
    db_session.flush()
    virgin.carbon_ef_id = ef_old.id
    db_session.commit()

    order = client.post(
        f"/api/v1/production-flow/recipes/{recipe.id}/production-orders",
        params={"qty_units": 1000, "approved_by": "Test Operatör"},
    ).json()
    client.post(f"/api/v1/production-flow/production-orders/{order['id']}/simulate-live-data")
    client.post(
        "/api/v1/production-flow/physical-verification",
        json={"production_order_id": order["id"], "tests": [
            {"test_type": "kalinlik", "value": 70.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None},
        ]},
    )
    finalize1 = client.post(f"/api/v1/production-flow/recipes/{recipe.id}/finalize")
    karbon_1 = finalize1.json()["per_1000_units"]["karbon_kg_co2"]

    # Kaynağı GERÇEKTEN değiştir -- farklı source/version/ef_value.
    ef_new = CarbonEmissionFactor(
        material_key="PE Virgin YENİ", factor_type="malzeme", ef_value=0.5, unit="kg_co2e_per_kg",
        source="Kaynak B - yeni EPD", year=2026, version="2.0", is_demo_placeholder=True,
    )
    db_session.add(ef_new)
    db_session.flush()
    virgin.carbon_ef_id = ef_new.id
    db_session.commit()

    # Yeniden hesapla (bu sistemde reaktif otomatik yeniden hesap yok --
    # finalize_result tekrar çağrılarak "yeniden hesaplama" tetiklenir).
    finalize2 = client.post(f"/api/v1/production-flow/recipes/{recipe.id}/finalize")
    karbon_2 = finalize2.json()["per_1000_units"]["karbon_kg_co2"]

    assert karbon_1 != karbon_2, "Karbon kaynağı değişince hesap GERÇEKTEN değişmeli"

    pdf_resp = client.get(f"/api/v1/production-flow/recipes/{recipe.id}/optimization-report")
    from io import BytesIO
    from pypdf import PdfReader
    pdf_text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(pdf_resp.content)).pages)
    assert "Kaynak B - yeni EPD" in pdf_text
    assert "2.0" in pdf_text


# --- Test 10: DPP V2'yi göstermeli ------------------------------------------

def test_10_dpp_v2yi_gosterir(client, db_session):
    _, virgin, pcr = _seed_materials(db_session)
    line, recipe = _seed_verified_line_recipe(db_session, virgin, pcr)

    order1 = client.post(
        f"/api/v1/production-flow/recipes/{recipe.id}/production-orders",
        params={"qty_units": 1000, "approved_by": "Test Operatör"},
    ).json()
    verify1 = client.post(
        "/api/v1/production-flow/physical-verification",
        json={"production_order_id": order1["id"], "tests": [
            {"test_type": "kalinlik", "value": 40.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None},
        ]},
    ).json()
    v2_id = verify1["new_recipe_version"]["id"]
    v2 = db_session.get(Recipe, v2_id)
    v2.line_id = line.id
    db_session.commit()

    order2 = client.post(
        f"/api/v1/production-flow/recipes/{v2_id}/production-orders",
        params={"qty_units": 1000, "approved_by": "Test Operatör"},
    ).json()
    client.post(f"/api/v1/production-flow/production-orders/{order2['id']}/simulate-live-data")
    client.post(
        "/api/v1/production-flow/physical-verification",
        json={"production_order_id": order2["id"], "tests": [
            {"test_type": "kalinlik", "value": 70.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None},
        ]},
    )
    client.post(f"/api/v1/production-flow/recipes/{v2_id}/finalize")

    passport_resp = client.post("/api/v1/passports", json={"recipe_id": v2_id})
    assert passport_resp.status_code == 200, passport_resp.text
    passport = passport_resp.json()
    assert passport["public"]["header"]["recipe_version"] == 2
    assert passport["public"]["header"]["recipe_id"] == v2_id
