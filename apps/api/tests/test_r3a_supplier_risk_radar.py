"""Faz R.3 (Madde 28) — Tedarikçi ve Hammadde Risk Radarı. Her sinyal
GERÇEK bir Material alanından türetilir; CoA/SDS AYRI izlenmediği dürüstçe
"uygunluk_belgeleri" kalemine yansır. Yeni 8. bileşen risk_service.py'ye
SADECE görüntüleme katmanı olarak eklendi -- scorer.py/aday sıralaması
etkilenmez (ayrı testle doğrulanır)."""
import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.main import app
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.risk_service import compute_risk_score
from app.services.supplier_risk_service import build_supplier_evidence_radar


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _polymer(db):
    p = db.query(Polymer).filter_by(code="PE").one_or_none()
    if p is None:
        p = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
        db.add(p)
        db.flush()
    return p


def test_empty_material_has_zero_percent_completeness(db_session):
    polymer = _polymer(db_session)
    material = Material(polymer_id=polymer.id, name="Boş Malzeme", material_type="virgin", food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8)
    db_session.add(material)
    db_session.commit()

    radar = build_supplier_evidence_radar(material)

    assert radar["tamlik_pct"] == 0.0
    assert all(not s["mevcut"] for s in radar["signals"].values())
    assert "CoA/SDS" in radar["signals"]["uygunluk_belgeleri"]["aciklama"] or "belge" in radar["signals"]["uygunluk_belgeleri"]["aciklama"]


def test_fully_documented_material_has_high_completeness(db_session):
    polymer = _polymer(db_session)
    material = Material(
        polymer_id=polymer.id, name="Tam Belgeli Malzeme", material_type="virgin",
        food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0,
        carbon_factor_kg_co2_per_kg=1.8, technical_datasheet_ref="TDS-001", source="Tedarikçi A",
        compliance_documents_ref="DOC-001", lot_number="LOT-2026-01", certification_status="Gıda sınıfı sertifikalı",
    )
    db_session.add(material)
    db_session.commit()

    radar = build_supplier_evidence_radar(material)

    # Karbon EF bağlı değil (carbon_ef_id yok) -- bu sinyal dolu SAYILMAZ,
    # dürüstçe eksik kalır. Diğer 5 sinyal dolu.
    assert radar["signals"]["karbon_ef_kaynagi"]["mevcut"] is False
    dolu_sayisi = sum(1 for s in radar["signals"].values() if s["mevcut"])
    assert dolu_sayisi == 5
    assert radar["tamlik_pct"] == round(5 / 6 * 100, 1)


def test_coa_and_sds_are_not_separately_fabricated(db_session):
    """CoA/SDS için ayrı bir alan olmadığı radar sinyal isimlerinden
    doğrulanır -- 'coa'/'sds' anahtarlı sinyal UYDURULMAMALI."""
    polymer = _polymer(db_session)
    material = Material(polymer_id=polymer.id, name="Test", material_type="virgin", food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8)
    db_session.add(material)
    db_session.commit()

    radar = build_supplier_evidence_radar(material)
    assert "coa" not in radar["signals"]
    assert "sds" not in radar["signals"]
    assert "uygunluk_belgeleri" in radar["signals"]


def _line(db):
    line = ProductionLine(name="Hat-1", layer_structure="A", layer_count=1, min_micron=10.0, max_micron=200.0)
    db.add(line)
    db.flush()
    return line


def _recipe_with_material(db, line, material):
    req = PackagingRequest(packaging_type="esnek film ambalaj", usage_area="t", product="t", target_market="AB", food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100})
    db.add(req)
    db.flush()
    recipe = Recipe(packaging_request_id=req.id, version=1, line_id=line.id, source="sistem_uretti", status="onerildi", total_micron=70.0)
    db.add(recipe)
    db.flush()
    db.add(RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0))
    db.commit()
    db.refresh(recipe)
    return recipe


def test_risk_score_includes_supplier_evidence_component(db_session):
    line = _line(db_session)
    polymer = _polymer(db_session)
    material = Material(polymer_id=polymer.id, name="Belgesiz Malzeme", material_type="virgin", food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8)
    db_session.add(material)
    db_session.commit()
    recipe = _recipe_with_material(db_session, line, material)

    result = compute_risk_score(db_session, recipe)

    assert "tedarikci_kanit_tamligi" in result["bilesenler"]
    dim = result["bilesenler"]["tedarikci_kanit_tamligi"]
    assert dim["risk_katkisi"] == "yuksek"  # tamamen belgesiz malzeme
    assert result["genel_risk"] == "yuksek"


def test_scorer_ranking_is_not_affected_by_supplier_evidence(db_session):
    """Faz R.3'ün 'mevcut risk skoru mantığını GENİŞLET, yeniden kurma'
    talimatı: scorer.py'nin skor/sıralama mantığı DEĞİŞMEMELİ."""
    from app.constraint_engine.types import LayerCandidate, MaterialSpec, RecipeCandidate
    from app.optimization.scorer import DEFAULT_WEIGHTS, score_candidate

    assert set(DEFAULT_WEIGHTS.keys()) == {
        "teknik_performans", "uretilebilirlik", "mevzuat_marji", "karbon", "fire_riski", "maliyet",
    }
    candidate = RecipeCandidate(
        layers=[LayerCandidate(
            layer_index=0, layer_label="A",
            material=MaterialSpec(id="m1", name="t", polymer_code="PE", material_type="virgin", food_contact_eligible=True, max_recommended_ratio_pct=100.0, degradation_factor=0.0, mfi_g_10min=None, cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8),
            ratio_pct=100.0, thickness_micron=70.0,
        )]
    )
    score = score_candidate(candidate, [], food_contact=False)
    assert set(score.breakdown.keys()) == {
        "teknik_performans", "uretilebilirlik", "mevzuat_marji", "karbon", "fire_riski", "maliyet",
    }


def test_http_supplier_evidence_radar_endpoint(client, db_session):
    polymer = _polymer(db_session)
    material = Material(polymer_id=polymer.id, name="Test HTTP", material_type="virgin", food_contact_eligible=True, max_recommended_ratio_pct=100.0, cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8, source="Tedarikçi B")
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)

    resp = client.get(f"/api/v1/materials/{material.id}/supplier-evidence-radar")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["signals"]["kaynak_tedarikci_kaniti"]["mevcut"] is True


def test_http_supplier_evidence_radar_404_for_unknown_material(client):
    resp = client.get("/api/v1/materials/olmayan-id/supplier-evidence-radar")
    assert resp.status_code == 404
