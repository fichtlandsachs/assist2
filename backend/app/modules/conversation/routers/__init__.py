"""Router registry for HeyKarl Conversation Engine."""
from fastapi import APIRouter

# Import routers from the flat source (backward-compatible)
from app.routers.ai import router as ai_router  # noqa: F401
from app.routers.agents import router as agents_router  # noqa: F401
from app.routers.admin_config import router as admin_config_router  # noqa: F401

# All routers in this domain
__all__ = ['ai_router', 'agents_router', 'admin_config_router']
