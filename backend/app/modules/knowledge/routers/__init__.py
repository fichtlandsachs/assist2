"""Router registry for HeyKarl KnowledgeBase / RAG."""
from fastapi import APIRouter

# Import routers from the flat source (backward-compatible)
from app.routers.rag_zones import router as rag_zones_router  # noqa: F401
from app.routers.external_sources import router as external_sources_router  # noqa: F401

# All routers in this domain
__all__ = ['rag_zones_router', 'external_sources_router']
