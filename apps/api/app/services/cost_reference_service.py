"""Faz F.10 — Maliyet kalemi çözümleme: firmanın kendi tesis-özel
`CostFactor`'ı (Faz B.7) her zaman önceliklidir; sadece firma o kalemi hiç
girmediyse `CostReferenceFactor` (bu fazda kurulan sistem-genel yedek)
"yalnızca yedek/gösterge" olarak kullanılabilir. F.12'nin merkezi
`resolve_value` fonksiyonuyla çözümlenir -- Faz B.7'nin kendi kapsam sınırı
(optimizasyon skorlamasına ENTEGRE EDİLMEZ) burada da korunur, bu SADECE bir
görünürlük/öneri katmanıdır."""
from sqlalchemy.orm import Session

from app.models.cost import CostFactor
from app.models.cost_reference import CostReferenceFactor
from app.services.data_resolution import Candidate, ResolvedValue, SourceTier, resolve_value

# app/models/cost.py'nin CostFactor alanlarıyla BİREBİR eşleşir.
_COST_TYPE_TO_FIELD: dict[str, str] = {
    "elektrik": "electricity_rate",
    "dogalgaz": "gas_rate",
    "iscilik": "labor_rate",
    "atik_bertaraf": "waste_disposal_cost",
    "geri_kazanim": "recovery_cost",
    "makine_saati": "machine_hour_rate",
}


def resolve_cost_component(db: Session, facility_id: str | None, cost_type: str) -> ResolvedValue | None:
    """FIRMA_URETIM (facility'nin kendi CostFactor kaydı) > SISTEM_REFERANS
    (CostReferenceFactor). Referans aralığının tek bir sayıya indirgenmesi
    gerektiğinde (bir CostFactor alanı tek bir oran taşır, bir aralık değil)
    aralığın ortası kullanılır -- bu bir ÖLÇÜM değildir, açıkça
    is_demo_placeholder ile işaretlenir."""
    field_name = _COST_TYPE_TO_FIELD.get(cost_type)
    if field_name is None:
        return None

    firm_value = None
    firm_currency = None
    if facility_id:
        cost_factor = (
            db.query(CostFactor)
            .filter_by(facility_id=facility_id)
            .order_by(CostFactor.effective_date.desc())
            .first()
        )
        if cost_factor is not None:
            firm_value = getattr(cost_factor, field_name)
            firm_currency = cost_factor.currency

    ref_row = db.query(CostReferenceFactor).filter_by(cost_type=cost_type).one_or_none()
    ref_value = None
    if ref_row is not None and ref_row.typical_min is not None and ref_row.typical_max is not None:
        ref_value = round((ref_row.typical_min + ref_row.typical_max) / 2, 4)

    candidates = [
        Candidate(
            tier=SourceTier.FIRMA_URETIM, value=firm_value, unit=firm_currency,
            source_text="Firma kendi tesis maliyet kaydı (CostFactor)", is_demo_placeholder=False,
        ),
        Candidate(
            tier=SourceTier.SISTEM_REFERANS, value=ref_value, unit=ref_row.unit if ref_row else None,
            source_text=ref_row.source if ref_row else None, year=ref_row.year if ref_row else None,
            version=ref_row.version if ref_row else None,
            is_demo_placeholder=ref_row.is_demo_placeholder if ref_row else True,
        ),
    ]
    return resolve_value(candidates)
