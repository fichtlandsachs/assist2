"""Router registry for System / Security."""
from fastapi import APIRouter

# Import routers from the flat source (backward-compatible)
from app.routers.superadmin import router as superadmin_router  # noqa: F401
from app.routers.superadmin_config import router as superadmin_config_router  # noqa: F401

# All routers in this domain
__all__ = ['superadmin_router', 'superadmin_config_router']
