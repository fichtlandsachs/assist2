"""Router registry for HeyKarl Integration Layer."""
from fastapi import APIRouter

# Import routers from the flat source (backward-compatible)
from app.routers.integrations import router as integrations_router  # noqa: F401
from app.routers.jira import router as jira_router  # noqa: F401
from app.routers.confluence import router as confluence_router  # noqa: F401
from app.routers.nextcloud import router as nextcloud_router  # noqa: F401
from app.routers.webhooks import router as webhooks_router  # noqa: F401
from app.routers.platform import router as platform_router  # noqa: F401

# All routers in this domain
__all__ = ['integrations_router', 'jira_router', 'confluence_router', 'nextcloud_router', 'webhooks_router', 'platform_router']
