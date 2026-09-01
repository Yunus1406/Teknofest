"""Faz K.2 (Madde 2) — Akıllı Başlangıç, Aşama 2'de girilen hedef kalınlığı
YOK SAYIP hattın min/max aralığının ortasını kullanıyordu (450 µm istenirken
70-71 µm üretiliyordu). Bu test önce bu hatayı üretir (düzeltmeden önce
KIRMIZI), sonra `packaging_service.generate_initial_recipe`'in hedefi
GERÇEKTEN kullandığını kilitler."""
from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.recipe import PackagingRequest
from app.services.packaging_service import generate_initial_recipe


def _material(db):
    # Faz K.6 -- polimer kodu GERÇEKTEN tercih edilen listedeki ("PP") bir
    # kodla eşleşmeli; artık uyumsuz bir kod sessizce herhangi bir virgin
    # malzemeye düşmüyor.
    polymer = Polymer(code="PP", name="Polipropilen K2", category="poliolefin", base_properties={})
    db.add(polymer)
    db.flush()
    m = Material(
        polymer_id=polymer.id, name="PP Virgin K2", material_type="virgin", density_g_cm3=0.905,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=38.0, carbon_factor_kg_co2_per_kg=1.9,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _request(db, target_thickness_micron=None):
    req = PackagingRequest(
        packaging_type="tamamen yeni tür k2", usage_area="test k2", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={},
        target_thickness_micron=target_thickness_micron,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def _line(db, min_micron, max_micron, layer_structure="A/B/A", layer_count=3):
    line = ProductionLine(
        name="Test Hat K2", layer_structure=layer_structure, layer_count=layer_count,
        min_micron=min_micron, max_micron=max_micron, supported_packaging_types=[],
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def test_generate_initial_recipe_uses_target_thickness_when_present(db_session):
    """450 µm hedeflenmiş bir talep + 20-120 µm aralığına sahip (ortası 70 µm
    olan) bir hat -- düzeltmeden ÖNCE reçete 70 µm çıkıyordu, ki bu 450'den
    tamamen farklı ve raporlanan hatanın birebir kaynağıydı."""
    _material(db_session)
    line = _line(db_session, min_micron=20.0, max_micron=120.0)
    req = _request(db_session, target_thickness_micron=450.0)

    recipe = generate_initial_recipe(db_session, req, line)

    assert recipe.total_micron == 450.0
    layer_sum = sum(layer.thickness_micron for layer in recipe.layers)
    assert abs(layer_sum - 450.0) < 0.01


def test_generate_initial_recipe_falls_back_to_line_midpoint_when_no_target(db_session):
    """Geriye dönük uyumluluk: hedef kalınlık HİÇ girilmemişse (None), eski
    davranış (hattın min/max ortası) korunmalı -- bu bir regresyon DEĞİL."""
    _material(db_session)
    line = _line(db_session, min_micron=20.0, max_micron=120.0)
    req = _request(db_session, target_thickness_micron=None)

    recipe = generate_initial_recipe(db_session, req, line)

    assert recipe.total_micron == 70.0
