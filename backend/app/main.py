import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import engine
from app.routers import agents, auth, epics, features, groups, integrations, memberships, organizations, plugins, roles, users, workflows, user_stories, inbox, calendar, test_cases, admin_config
from app.routers.pdf_settings import router as pdf_settings_router
from app.routers.nextcloud import router as nextcloud_router
from app.routers.ai import router as ai_router
from app.routers.superadmin import router as superadmin_router
from app.routers.superadmin_config import router as superadmin_config_router
from app.routers.auth_atlassian import router as auth_atlassian_router
from app.routers.auth_github import router as auth_github_router
from app.routers.jira import router as jira_router
from app.routers.projects import router as projects_router
from app.routers.stats import router as stats_router
from app.routers.contact import router as contact_router
from app.routers.suggestions import router as suggestions_router
from app.routers.confluence import router as confluence_router
from app.routers.webhooks import router as webhooks_router
from app.routers.evaluations import router as evaluations_router
from app.routers.processes import router as processes_router
from app.routers.rule_sets import router as rule_sets_router
from app.routers.scoring_profiles import router as scoring_profiles_router
from app.routers.story_versions import router as story_versions_router
from app.routers.story_readiness import router as story_readiness_router
from app.routers.billing import router as billing_router
from app.routers.refinement import router as refinement_router
from app.routers.story_assistant import router as story_assistant_router

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("AI-Native Workspace Platform API is ready")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    yield
    # Shutdown
    await engine.dispose()
    logger.info("Database engine disposed. Shutdown complete.")


app = FastAPI(
    title="AI-Native Workspace Platform API",
    description="Backend API for the AI-Native Workspace Platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "code": f"HTTP_{exc.status_code}",
            "details": {},
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": str(exc),
            "code": "VALIDATION_ERROR",
            "details": {},
        },
    )


# Health Check
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {"status": "ok", "environment": settings.ENVIRONMENT}


# Mount Routers
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(users.router, prefix="/api/v1", tags=["Users"])
app.include_router(organizations.router, prefix="/api/v1", tags=["Organizations"])
app.include_router(memberships.router, prefix="/api/v1", tags=["Memberships"])
app.include_router(roles.router, prefix="/api/v1", tags=["Roles"])
app.include_router(groups.router, prefix="/api/v1", tags=["Groups"])
app.include_router(plugins.router, prefix="/api/v1", tags=["Plugins"])
app.include_router(workflows.router, prefix="/api/v1", tags=["Workflows"])
app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])
app.include_router(integrations.router, prefix="/api/v1", tags=["Integrations"])
app.include_router(epics.router, prefix="/api/v1", tags=["Epics"])
app.include_router(features.router, prefix="/api/v1", tags=["Features"])
app.include_router(user_stories.router, prefix="/api/v1", tags=["UserStories"])
app.include_router(inbox.router, prefix="/api/v1", tags=["Inbox"])
app.include_router(calendar.router, prefix="/api/v1", tags=["Calendar"])
app.include_router(test_cases.router, prefix="/api/v1", tags=["TestCases"])
app.include_router(admin_config.router, prefix="/api/v1", tags=["AdminConfig"])
app.include_router(pdf_settings_router, prefix="/api/v1", tags=["PDF Settings"])
app.include_router(nextcloud_router, prefix="/api/v1", tags=["Nextcloud"])
app.include_router(ai_router, prefix="/api/v1", tags=["AI"])
app.include_router(superadmin_router)
app.include_router(superadmin_config_router)
app.include_router(auth_atlassian_router, prefix="/api/v1")
app.include_router(auth_github_router, prefix="/api/v1")
app.include_router(jira_router, prefix="/api/v1", tags=["Jira"])
app.include_router(stats_router, prefix="/api/v1", tags=["Stats"])
app.include_router(projects_router, prefix="/api/v1", tags=["Projects"])
app.include_router(contact_router, prefix="/api/v1", tags=["Contact"])
app.include_router(suggestions_router, prefix="/api/v1", tags=["Suggestions"])
app.include_router(confluence_router, prefix="/api/v1", tags=["Confluence"])
app.include_router(webhooks_router, prefix="/api/v1", tags=["Webhooks"])
app.include_router(evaluations_router, prefix="/api/v1", tags=["Evaluations"])
app.include_router(processes_router, prefix="/api/v1", tags=["Processes"])
app.include_router(rule_sets_router)
app.include_router(scoring_profiles_router)
app.include_router(story_versions_router)
app.include_router(story_readiness_router, prefix="/api/v1", tags=["Story Readiness"])
app.include_router(billing_router, prefix="/api/v1", tags=["Billing"])
app.include_router(refinement_router, prefix="/api/v1", tags=["Refinement"])
app.include_router(story_assistant_router, prefix="/api/v1", tags=["StoryAssistant"])
