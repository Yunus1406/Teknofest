from fastapi import APIRouter

from app.api.v1.routers import (
    cost,
    dashboard1,
    knowledge,
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
