from fastapi import APIRouter

from app.api.v1.routers import (
    company,
    cost,
    dashboard1,
    knowledge,
    machine_park,
    material_library,
    optimization,
    packaging_flow,
    passport,
    product_sku,
    production_flow,
    traceability,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(dashboard1.router)
api_router.include_router(knowledge.router)
api_router.include_router(product_sku.router)
api_router.include_router(cost.router)
api_router.include_router(packaging_flow.router)
api_router.include_router(optimization.router)
api_router.include_router(production_flow.router)
api_router.include_router(traceability.router)
api_router.include_router(passport.router)
api_router.include_router(company.router)
api_router.include_router(machine_park.router)
api_router.include_router(material_library.router)
