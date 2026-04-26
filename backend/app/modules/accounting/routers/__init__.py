"""Router registry for Accounting."""
from fastapi import APIRouter

# Import routers from the flat source (backward-compatible)
from app.routers.billing import router as billing_router  # noqa: F401

# All routers in this domain
__all__ = ['billing_router']
