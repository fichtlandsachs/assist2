import logging
from fastapi import FastAPI

from app.config import get_settings
from app.routers.workflows import router as workflows_router

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="langgraph-service", version="1.0.0", docs_url=None, redoc_url=None)
app.include_router(workflows_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
