"""Faz R.1 (Madde 26) — Ambalaj Yaşam Döngüsü Zaman Çizelgesi. Yeni bir
tablo/veri modeli YOK -- `learning_memory_service.causal_chain_for_recipe()`
(Faz I.3/Q.2) DEĞİŞTİRİLMEDEN çağrılır ve GERÇEK ek olay kaynaklarıyla
(PackagingRequest/OptimizationRun/ProductionOrder/SustainabilityResult/
RegulationRequirement) tek, kronolojik bir "olay türü" listesine
zenginleştirilir. Hiçbir şey persist edilmez -- Faz O/P/Q'nun
"compute-on-read" disipliniyle aynı. Bir olay kaynağı yoksa (ör. hiç pilot
üretim yapılmadıysa) o olay türü HİÇ üretilmez, uydurulmaz."""
from sqlalchemy.orm import Session

from app.models.knowledge import Regulation
from app.models.optimization import OptimizationRun
from app.models.production import PhysicalTest, ProductionOrder, SustainabilityResult
from app.models.recipe import PackagingRequest, Recipe, RegulatoryAssessment
from app.models.regulation_requirement import RegulationRequirement
from app.services.learning_memory_service import causal_chain_for_recipe
from app.services.packaging_service import _current_requirement_version


def _mevzuat_guncellendi_events(db: Session, packaging_request: PackagingRequest) -> list[dict]:
    """Faz L.3/L.4'ün AYNI karşılaştırmasını (`_current_requirement_version`
    ile GÜNCEL versiyon vs `RegulatoryAssessment.regulation_version_snapshot`
    ile o an dondurulmuş versiyon) reuse eder -- yeniden kurulmaz. Sadece
    GERÇEK bir `RegulationRequirement.changed_at` zaman damgası varsa olay
    üretilir."""
    events: list[dict] = []
    assessments = db.query(RegulatoryAssessment).filter_by(packaging_request_id=packaging_request.id).all()
    for a in assessments:
        if a.regulation_version_snapshot is None:
            continue
        current_version = _current_requirement_version(db, a.regulation_id)
        if current_version is None or current_version == a.regulation_version_snapshot:
            continue
        row = (
            db.query(RegulationRequirement)
            .filter_by(regulation_id=a.regulation_id)
            .order_by(RegulationRequirement.target_year)
            .first()
        )
        if row is None or row.changed_at is None:
            continue
        reg = db.get(Regulation, a.regulation_id)
        events.append(
            {
                "event_type": "mevzuat_guncellendi",
                "baslik": f"{reg.code if reg is not None else '—'} Mevzuatı Güncellendi",
                "tarih": row.changed_at,
                "detay": {
                    "regulation_code": reg.code if reg is not None else None,
                    "eski_versiyon": a.regulation_version_snapshot,
                    "yeni_versiyon": current_version,
                    "degisiklik_ozeti": row.change_summary,
                },
            }
        )
    return events


def build_lifecycle_timeline(db: Session, recipe_id: str) -> list[dict] | None:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        return None

    chain_nodes = causal_chain_for_recipe(db, recipe)
    root_recipe_id = chain_nodes[0]["id"] if chain_nodes else recipe.id
    root = db.get(Recipe, root_recipe_id)
    packaging_request = root.packaging_request if root is not None else None

    events: list[dict] = []

    if packaging_request is not None:
        events.append(
            {
                "event_type": "sartname_olusturuldu",
                "baslik": "Teknik Şartname Oluşturuldu",
                "tarih": packaging_request.created_at,
                "detay": {"packaging_type": packaging_request.packaging_type, "product": packaging_request.product},
            }
        )
        for run in db.query(OptimizationRun).filter_by(packaging_request_id=packaging_request.id).all():
            events.append(
                {
                    "event_type": "optimizasyon_calistirildi",
                    "baslik": "Optimizasyon Çalıştırıldı",
                    "tarih": run.created_at,
                    "detay": {
                        "run_id": run.id,
                        "generated_candidate_count": run.parameters.get("candidate_count_generated"),
                    },
                }
            )

    for node in chain_nodes:
        node_recipe = db.get(Recipe, node["id"])
        events.append(
            {
                "event_type": "recete_uretildi" if node["version"] == 1 else "recete_revize_edildi",
                "baslik": f"Reçete V{node['version']} {'Üretildi' if node['version'] == 1 else 'Revize Edildi'}",
                "tarih": node["created_at"],
                "detay": {
                    "recipe_id": node["id"],
                    "diff_from_previous": node["diff_from_previous"],
                    "outcome": node["outcome"],
                    "basarisizlik_nedeni": node["basarisizlik_nedeni"],
                },
            }
        )

        orders = db.query(ProductionOrder).filter_by(recipe_id=node["id"]).order_by(ProductionOrder.created_at).all()
        for order in orders:
            events.append(
                {
                    "event_type": "pilot_uretim",
                    "baslik": f"Pilot Üretim (V{node['version']})",
                    "tarih": order.created_at,
                    "detay": {"production_order_id": order.id, "status": order.status},
                }
            )

        tests = db.query(PhysicalTest).filter_by(recipe_id=node["id"]).order_by(PhysicalTest.created_at).all()
        if tests:
            events.append(
                {
                    "event_type": "fiziksel_test",
                    "baslik": f"Fiziksel Test (V{node['version']})",
                    "tarih": tests[0].created_at,
                    "detay": node["physical_test_summary"],
                }
            )

        if node_recipe is not None and node_recipe.is_verified:
            result = (
                db.query(SustainabilityResult)
                .filter_by(recipe_id=node["id"], is_actual=True)
                .order_by(SustainabilityResult.created_at)
                .first()
            )
            if result is not None:
                events.append(
                    {
                        "event_type": "uretime_serbest_birakildi",
                        "baslik": f"Üretime Serbest Bırakıldı (V{node['version']})",
                        "tarih": result.created_at,
                        "detay": {"recipe_id": node["id"]},
                    }
                )

    if packaging_request is not None:
        events.extend(_mevzuat_guncellendi_events(db, packaging_request))

    events.sort(key=lambda e: e["tarih"])
    return events
