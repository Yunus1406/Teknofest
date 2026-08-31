"""Faz B.7 — Maliyet Veri Tabanı model doğrulaması. Bu fazın kapsamı SADECE
saklama olduğundan (scorer.py'ye entegrasyon kapsam dışı), testler modelin
Facility'ye doğru bağlandığını ve demo/gerçek veri ayrımının (is_demo_
placeholder) doğru taşındığını doğrular."""
import pytest

from app.models.company import Company, Facility
from app.models.cost import CostFactor


@pytest.fixture()
def facility(db_session):
    company = Company(name="Test Firma")
    db_session.add(company)
    db_session.flush()
    facility = Facility(company_id=company.id, name="Test Tesis")
    db_session.add(facility)
    db_session.commit()
    db_session.refresh(facility)
    return facility


def test_cost_factor_links_to_facility(db_session, facility):
    cf = CostFactor(
        facility_id=facility.id,
        currency="TRY",
        electricity_rate=3.2,
        gas_rate=18.5,
        labor_rate=180.0,
        waste_disposal_cost=4.5,
        recovery_cost=2.0,
        machine_hour_rate=650.0,
        is_demo_placeholder=True,
        source="DEMO/VARSAYIMSAL",
    )
    db_session.add(cf)
    db_session.commit()
    db_session.refresh(cf)

    assert cf.facility_id == facility.id
    assert cf.currency == "TRY"
    assert cf.electricity_rate == pytest.approx(3.2)
    assert cf.is_demo_placeholder is True
    assert cf.effective_date is not None


def test_cost_factor_rates_are_nullable_when_unknown(db_session, facility):
    """Gerçek bir tesisin henüz tüm kalemleri (ör. doğalgaz kullanmıyor
    olabilir) bilinmeyebilir — kısıt alanları rastgele bir değerle
    doldurmaya ZORLAMAMALI, None kalabilmeli."""
    cf = CostFactor(facility_id=facility.id, gas_rate=None, is_demo_placeholder=True)
    db_session.add(cf)
    db_session.commit()
    db_session.refresh(cf)

    assert cf.gas_rate is None
    assert cf.electricity_rate is None
