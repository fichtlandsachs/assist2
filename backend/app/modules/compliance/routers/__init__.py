"""Router registry for HeyKarl Compliance Engine."""
from fastapi import APIRouter

# Import routers from the flat source (backward-compatible)
from app.routers.compliance import router as compliance_router  # noqa: F401
from app.routers.compliance_chat import router as compliance_chat_router  # noqa: F401
from app.routers.controls import router as controls_router  # noqa: F401
from app.routers.control_standards import router as control_standards_router  # noqa: F401
from app.routers.product_governance import router as product_governance_router  # noqa: F401
from app.routers.rule_sets import router as rule_sets_router  # noqa: F401
from app.routers.scoring_profiles import router as scoring_profiles_router  # noqa: F401
from app.routers.trust_admin import router as trust_admin_router  # noqa: F401

# All routers in this domain
__all__ = ['compliance_router', 'compliance_chat_router', 'controls_router', 'control_standards_router', 'product_governance_router', 'rule_sets_router', 'scoring_profiles_router', 'trust_admin_router']
