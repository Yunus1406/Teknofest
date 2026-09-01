"""Faz O.1 (Madde 18) — Ambalajın Dijital İkizi. Faz B.9'un
`traceability_service.build_recipe_traceability()` zincirine (Reçete +
Katman + Makine + Test + Mevzuat) Proses (ProcessReference), Enerji/
Karbon/Fire (SustainabilityResult) ve Versiyon Zinciri katılarak TEK bir
birleşik görünüm oluşturulur. Yeni bir tablo YOK, hiçbir şey
önbelleklenmez -- `passport_service.build_passport_content()` ile AYNI
disiplin: her çağrı DB'nin GÜNCEL halinden taze hesaplanır, bu yüzden
reçete/üretim verisi değiştiğinde (yeni versiyon açıldığında) görünüm
OTOMATİK güncel kalır -- statik bir anlık görüntü DEĞİLDİR."""
from sqlalchemy.orm import Session

from app.models.infrastructure import ProductionLine
from app.models.production import SustainabilityResult
from app.models.recipe import Recipe
from app.models.technical_reference import ProcessReference
from app.services import production_flow_service, traceability_service
from app.services.report_service import _sustainability_result_for


def _sustainability_snapshot(db: Session, recipe_id: str) -> dict | None:
    """`report_service._sustainability_result_for()` SADECE `is_actual=True`
    (gerçekleşen) satırı arar -- reçete henüz üretilmediyse (Aşama 8'in
    tahmini) bilinçli olarak None döner. Dijital İkiz üretim ÖNCESİ bir
    reçete için de anlamlı olmalı, bu yüzden burada gerçekleşen yoksa
    tahminiye (is_actual=False) düşülür -- ikisi ASLA karıştırılmaz, hangisi
    olduğu ayrı bir alanla (`is_actual`) taşınır."""
    actual = _sustainability_result_for(db, recipe_id)
    if actual is not None:
        return {"is_actual": True, **actual}
    row = (
        db.query(SustainabilityResult)
        .filter_by(recipe_id=recipe_id, is_actual=False)
        .order_by(SustainabilityResult.created_at.desc())
        .first()
    )
    return {"is_actual": False, **row.per_1000_units} if row is not None else None


def build_digital_twin(db: Session, recipe_id: str) -> dict | None:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        return None

    traceability = traceability_service.build_recipe_traceability(db, recipe_id)

    line = db.get(ProductionLine, recipe.line_id) if recipe.line_id else None
    process_parameters: list[dict] = []
    if line is not None and line.process_type:
        rows = db.query(ProcessReference).filter_by(process_type=line.process_type).all()
        process_parameters = [
            {
                "parameter_name": r.parameter_name,
                "typical_min": r.typical_min,
                "typical_max": r.typical_max,
                "unit": r.unit,
                "source": r.source,
                "is_demo_placeholder": r.is_demo_placeholder,
            }
            for r in rows
        ]

    return {
        "traceability": traceability,
        "process_parameters": process_parameters,
        "sustainability_per_1000_units": _sustainability_snapshot(db, recipe.id),
        "version_history": production_flow_service.version_history(db, recipe),
    }
