"""Tüm ORM modelleri burada import edilir ki Base.metadata (Alembic /
create_all) her tabloyu görsün."""
from app.models.base import Base  # noqa: F401
from app.models.chemical_restriction import ChemicalRestriction  # noqa: F401
from app.models.company import Company, Facility  # noqa: F401
from app.models.cost import CostFactor  # noqa: F401
from app.models.cost_reference import BenchmarkReference, CostReferenceFactor  # noqa: F401
from app.models.digital_product_passport import DigitalProductPassport  # noqa: F401
from app.models.food_contact_requirement import FoodContactRequirement  # noqa: F401
from app.models.infrastructure import LineMaterialCompatibility, ProductionLine  # noqa: F401
from app.models.knowledge import (  # noqa: F401
    Additive,
    CarbonEmissionFactor,
    Material,
    PcrMaterial,
    PirMaterial,
    Polymer,
    Regulation,
)
from app.models.mechanical_test_standard import MechanicalTestStandard  # noqa: F401
from app.models.optimization import OptimizationCandidate, OptimizationRun  # noqa: F401
from app.models.product_sku import ProductSku  # noqa: F401
from app.models.regulation_requirement import RegulationRequirement  # noqa: F401
from app.models.recyclability_criterion import RecyclabilityCriterion  # noqa: F401
from app.models.technical_reference import (  # noqa: F401
    LayerStructureReference,
    PolymerTechnicalReference,
    ProcessReference,
)
from app.models.production import (  # noqa: F401
    PhysicalTest,
    ProductionLiveData,
    ProductionOrder,
    SustainabilityResult,
    WasteRecord,
)
from app.models.recipe import (  # noqa: F401
    PackagingRequest,
    Recipe,
    RecipeAdditive,
    RecipeEvaluation,
    RecipeLayer,
    RecipeMetric,
    RegulatoryAssessment,
)

__all__ = [
    "Base",
    "ChemicalRestriction",
    "Company",
    "Facility",
    "CostFactor",
    "CostReferenceFactor",
    "BenchmarkReference",
    "DigitalProductPassport",
    "FoodContactRequirement",
    "Polymer",
    "Material",
    "PcrMaterial",
    "PirMaterial",
    "CarbonEmissionFactor",
    "Additive",
    "Regulation",
    "RegulationRequirement",
    "PolymerTechnicalReference",
    "ProcessReference",
    "LayerStructureReference",
    "MechanicalTestStandard",
    "RecyclabilityCriterion",
    "ProductionLine",
    "LineMaterialCompatibility",
    "ProductSku",
    "PackagingRequest",
    "RegulatoryAssessment",
    "Recipe",
    "RecipeLayer",
    "RecipeAdditive",
    "RecipeEvaluation",
    "RecipeMetric",
    "OptimizationRun",
    "OptimizationCandidate",
    "ProductionOrder",
    "ProductionLiveData",
    "WasteRecord",
    "PhysicalTest",
    "SustainabilityResult",
]
