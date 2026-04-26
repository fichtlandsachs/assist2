"""Router registry for HeyKarl Core."""
from fastapi import APIRouter

# Import routers from the flat source (backward-compatible)
from app.routers.auth import router as auth_router  # noqa: F401
from app.routers.auth_atlassian import router as auth_atlassian_router  # noqa: F401
from app.routers.auth_github import router as auth_github_router  # noqa: F401
from app.routers.users import router as users_router  # noqa: F401
from app.routers.organizations import router as organizations_router  # noqa: F401
from app.routers.memberships import router as memberships_router  # noqa: F401
from app.routers.roles import router as roles_router  # noqa: F401
from app.routers.groups import router as groups_router  # noqa: F401
from app.routers.user_stories import router as user_stories_router  # noqa: F401
from app.routers.epics import router as epics_router  # noqa: F401
from app.routers.projects import router as projects_router  # noqa: F401
from app.routers.features import router as features_router  # noqa: F401
from app.routers.story_versions import router as story_versions_router  # noqa: F401
from app.routers.refinement import router as refinement_router  # noqa: F401
from app.routers.story_readiness import router as story_readiness_router  # noqa: F401
from app.routers.story_assistant import router as story_assistant_router  # noqa: F401
from app.routers.suggestions import router as suggestions_router  # noqa: F401
from app.routers.test_cases import router as test_cases_router  # noqa: F401
from app.routers.evaluations import router as evaluations_router  # noqa: F401
from app.routers.processes import router as processes_router  # noqa: F401
from app.routers.workflows import router as workflows_router  # noqa: F401
from app.routers.bcm import router as bcm_router  # noqa: F401
from app.routers.capabilities import router as capabilities_router  # noqa: F401
from app.routers.stats import router as stats_router  # noqa: F401
from app.routers.plugins import router as plugins_router  # noqa: F401
from app.routers.inbox import router as inbox_router  # noqa: F401
from app.routers.contact import router as contact_router  # noqa: F401
from app.routers.pdf_settings import router as pdf_settings_router  # noqa: F401

# All routers in this domain
__all__ = ['auth_router', 'auth_atlassian_router', 'auth_github_router', 'users_router', 'organizations_router', 'memberships_router', 'roles_router', 'groups_router', 'user_stories_router', 'epics_router', 'projects_router', 'features_router', 'story_versions_router', 'refinement_router', 'story_readiness_router', 'story_assistant_router', 'suggestions_router', 'test_cases_router', 'evaluations_router', 'processes_router', 'workflows_router', 'bcm_router', 'capabilities_router', 'stats_router', 'plugins_router', 'inbox_router', 'contact_router', 'pdf_settings_router']
