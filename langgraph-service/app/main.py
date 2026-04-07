import logging
from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="langgraph-service", version="1.0.0", docs_url=None, redoc_url=None)


@app.get("/health")
async def health():
    return {"status": "ok"}
