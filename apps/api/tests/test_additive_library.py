"""Faz B.4 — Masterbatch/Katkı kütüphanesi genişletmesi."""
from app.knowledge_base.loader import load_all
from app.models.knowledge import Additive
from app.services.carbon import TANIMLI_DEMO, resolve_carbon_ef


def test_additive_model_carries_manufacturer_carrier_and_cost(db_session):
    additive = Additive(
        name="Test Masterbatch", additive_type="stabilizator", manufacturer="Test A.Ş.",
        carrier_polymer="PP", regulatory_document_ref="EU 10/2011 Uygunluk Beyanı Mevcut",
        dosage_min_pct=0.5, dosage_max_pct=2.0, food_contact_eligible=True, cost_per_kg=85.0,
    )
    db_session.add(additive)
    db_session.commit()

    assert additive.manufacturer == "Test A.Ş."
    assert additive.carrier_polymer == "PP"
    assert additive.cost_per_kg == 85.0


def test_seeded_additives_are_linked_to_carbon_emission_factors(db_session):
    """Faz B.2'de kurulan karbon EF çözümleme mekanizması Additive için de
    çalışmalı — tüm seed katkıları DEMO/VARSAYIMSAL etiketli bir EF'e bağlı olmalı."""
    load_all(db_session)

    additives = db_session.query(Additive).all()
    assert len(additives) == 6  # şişirilmiş değil, mevcut 6 katkı zenginleştirildi

    for a in additives:
        assert a.carbon_ef_id is not None, f"{a.name} bir karbon EF'ine bağlı değil"
        value, status, source = resolve_carbon_ef(a)
        assert status == TANIMLI_DEMO
        assert value > 0


def test_loader_is_idempotent_for_additives(db_session):
    """Aynı seed iki kez çalıştırıldığında tekrar satır oluşturmamalı,
    var olanı güncellemeli."""
    load_all(db_session)
    count_first = db_session.query(Additive).count()
    load_all(db_session)
    count_second = db_session.query(Additive).count()
    assert count_first == count_second == 6
