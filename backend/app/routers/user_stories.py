import json
import logging
import re
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

import httpx

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.deps import get_current_user
from app.core.billing_guard import require_active_subscription
from app.models.user import User
from app.models.user_story import UserStory, StoryStatus
from app.models.test_case import TestCase
from app.schemas.test_case import TestCaseRead
from app.schemas.user_story import (
    AISuggestRequest,
    AISuggestResponse,
    AITestCaseSuggestResponse,
    AIDoDSuggestResponse,
    EpicCreate,
    EpicRead,
    StoryDocsSave,
    StoryDocsRead,
    StorySplitSuggestion,
    StorySplitSave,
    StorySplitResult,
    StoryScoreResponse,
    UserStoryCreate,
    UserStoryRead,
    UserStoryUpdate,
)
from app.services.ai_story_service import (
    _get_learning_flags,
    get_story_suggestions,
    generate_story_docs,
    generate_test_case_suggestions,
    generate_dod_suggestions,
    generate_feature_suggestions,
    split_story,
    DocsGenerateRequest,
    DocsGenerateResponse,
)
from app.schemas.feature import AIFeatureSuggestion, AIFeatureSuggestResponse
from app.models.epic import Epic
from app.services import confluence_service
from app.services import org_integrations_service as integrations_svc
from app.services.nextcloud_service import nextcloud_service
from app.models.organization import Organization
from app.ai.context_analyzer import analyze_context
from app.ai.complexity_scorer import score_complexity
from app.core.exceptions import NotFoundException
from app.tasks.agent_tasks import analyze_story_task
from app.tasks.embedding_tasks import embed_story_task
from app.tasks.pdf_tasks import generate_story_pdf
from app.tasks.rag_tasks import index_story_knowledge
from app.models.pdf_settings import PdfSettings
from app.models.feature import Feature
from app.models.project import Project
from app.services.pdf_service import pdf_service
from app.services.jira_service import jira_service
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _check_llm_allowed(org_id: uuid.UUID, db: AsyncSession) -> None:
    """Raise 503 when the org's admin config has retrieval_only=True."""
    flags = await _get_learning_flags(org_id, db)
    if flags.get("retrieval_only"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="KI-Generierung deaktiviert: Retrieval-only Modus ist aktiv (Admin-Konfiguration).",
        )


async def _get_ai_settings(org_id: uuid.UUID, db: AsyncSession) -> Optional[dict]:
    """Load org-level AI settings (provider + decrypted key). Returns None on failure."""
    try:
        org_stmt = select(Organization).where(Organization.id == org_id)
        org_result = await db.execute(org_stmt)
        org = org_result.scalar_one_or_none()
        if org:
            return integrations_svc.get_ai_client_settings(org)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Background doc regeneration
# ---------------------------------------------------------------------------

async def _regenerate_docs_bg(
    story_id: uuid.UUID,
    org_id: uuid.UUID,
    title: str,
    description: Optional[str],
    acceptance_criteria: Optional[str],
) -> None:
    """Generate docs via AI and persist them on the story (runs in background)."""
    try:
        async with AsyncSessionLocal() as db:
            ai_settings = await _get_ai_settings(org_id, db)
            docs = await generate_story_docs(
                DocsGenerateRequest(
                    title=title,
                    description=description,
                    acceptance_criteria=acceptance_criteria,
                ),
                ai_settings=ai_settings,
            )
            docs_dict = {
                "changelog_entry": docs.changelog_entry,
                "pdf_outline": docs.pdf_outline,
                "summary": docs.summary,
                "technical_notes": docs.technical_notes,
            }
            stmt = select(UserStory).where(UserStory.id == story_id)
            result = await db.execute(stmt)
            story = result.scalar_one_or_none()
            if story:
                story.generated_docs = json.dumps(docs_dict, ensure_ascii=False)
                await db.commit()
                logger.info("Docs regenerated for story %s", story_id)
    except Exception as exc:
        logger.error("Doc regeneration failed for story %s: %s", story_id, exc)


@router.get(
    "/user-stories",
    response_model=List[UserStoryRead],
    summary="List user stories for an organization",
)
async def list_user_stories(
    org_id: uuid.UUID,
    project_id: Optional[uuid.UUID] = None,
    epic_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[UserStoryRead]:
    """List all user stories for the given organization."""
    stmt = (
        select(UserStory)
        .where(UserStory.organization_id == org_id)
        .order_by(UserStory.created_at.desc())
    )
    if project_id is not None:
        stmt = stmt.where(UserStory.project_id == project_id)
    if epic_id is not None:
        stmt = stmt.where(UserStory.epic_id == epic_id)
    result = await db.execute(stmt)
    stories = result.scalars().all()
    return [UserStoryRead.model_validate(s) for s in stories]


@router.post(
    "/user-stories",
    response_model=UserStoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user story",
)
async def create_user_story(
    org_id: uuid.UUID,
    data: UserStoryCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _billing=Depends(require_active_subscription),
) -> UserStoryRead:
    """Create a new user story in the given organization."""
    story = UserStory(
        organization_id=org_id,
        created_by_id=current_user.id,
        title=data.title,
        description=data.description,
        acceptance_criteria=data.acceptance_criteria,
        definition_of_done=data.definition_of_done,
        priority=data.priority,
        story_points=data.story_points,
        epic_id=data.epic_id,
        project_id=data.project_id,
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)
    background_tasks.add_task(
        _regenerate_docs_bg, story.id, org_id, story.title, story.description, story.acceptance_criteria
    )
    analyze_story_task.delay(str(story.id), str(org_id))
    embed_story_task.delay(str(story.id), str(org_id))
    # Index into document_chunks so the chat RAG can find this story immediately
    from app.models.organization import Organization as _Org
    _org_res = await db.execute(select(_Org).where(_Org.id == org_id))
    _org = _org_res.scalar_one_or_none()
    _org_slug = _org.slug if _org else str(org_id)
    index_story_knowledge.delay(str(story.id), str(org_id), _org_slug)
    return UserStoryRead.model_validate(story)


@router.get(
    "/user-stories/{story_id}",
    response_model=UserStoryRead,
    summary="Get a user story",
)
async def get_user_story(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserStoryRead:
    """Get a specific user story by ID."""
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")
    return UserStoryRead.model_validate(story)


@router.patch(
    "/user-stories/{story_id}",
    response_model=UserStoryRead,
    summary="Update a user story",
)
async def update_user_story(
    story_id: uuid.UUID,
    data: UserStoryUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserStoryRead:
    """Update a user story."""
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")

    update_data = data.model_dump(exclude_unset=True)
    doc_fields = {"title", "description", "acceptance_criteria"}
    needs_regen = bool(doc_fields & update_data.keys())

    # Quality gate: block advancement to ready/in_progress/testing/done if quality_score < 80
    GATED_STATUSES = {"ready", "in_progress", "testing", "done"}
    MIN_QUALITY = 80
    new_status = update_data.get("status")
    if (
        new_status in GATED_STATUSES
        and story.quality_score is not None
        and story.quality_score < MIN_QUALITY
    ):
        raise HTTPException(
            status_code=422,
            detail=f"Quality-Score {story.quality_score}/100 ist zu niedrig (Minimum: {MIN_QUALITY}). Bitte die Story zuerst im Assistenten analysieren und verbessern.",
        )

    old_status = story.status

    for field, value in update_data.items():
        setattr(story, field, value)

    await db.commit()
    await db.refresh(story)

    # Dispatch PDF generation when story transitions to done
    if data.status is not None and data.status == StoryStatus.done and old_status != StoryStatus.done:
        generate_story_pdf.delay(str(story.id), str(story.organization_id))

    # Re-index story knowledge whenever content or status changes
    _content_changed = any(
        k in update_data for k in ("title", "description", "acceptance_criteria", "status")
    )
    if _content_changed:
        from app.models.organization import Organization
        org_result = await db.execute(
            select(Organization).where(Organization.id == story.organization_id)
        )
        org = org_result.scalar_one_or_none()
        org_slug = org.slug if org else str(story.organization_id)
        index_story_knowledge.delay(str(story.id), str(story.organization_id), org_slug)

    if needs_regen:
        background_tasks.add_task(
            _regenerate_docs_bg, story.id, story.organization_id, story.title, story.description, story.acceptance_criteria
        )
        embed_story_task.delay(str(story.id), str(story.organization_id))

    return UserStoryRead.model_validate(story)


@router.delete(
    "/user-stories/{story_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user story",
)
async def delete_user_story(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a user story."""
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")
    await db.delete(story)
    await db.commit()


@router.post(
    "/user-stories/{story_id}/score",
    response_model=StoryScoreResponse,
    summary="Score Story Quality (Heuristic)",
)
async def score_user_story(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StoryScoreResponse:
    """Run heuristic scoring on a story. No DB write, no LLM."""
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")

    context = analyze_context(story.title, story.description, story.acceptance_criteria)
    complexity = score_complexity(context)

    return StoryScoreResponse(
        level=complexity.level,
        confidence=complexity.confidence,
        clarity=context.clarity,
        complexity=context.complexity,
        risk=context.risk,
        domain=context.domain,
    )


@router.post(
    "/user-stories/{story_id}/validate",
    response_model=UserStoryRead,
    summary="Run AI quality validation and persist score on a story",
)
async def validate_user_story(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserStoryRead:
    """Run AI quality analysis, persist quality_score + ai_suggestions, return updated story."""
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")

    await _check_llm_allowed(story.organization_id, db)
    ai_settings = await _get_ai_settings(story.organization_id, db)

    data = AISuggestRequest(
        title=story.title,
        description=story.description,
        acceptance_criteria=story.acceptance_criteria,
        story_id=story_id,
    )
    suggestion = await get_story_suggestions(data, ai_settings=ai_settings, org_id=story.organization_id, db=db)

    # ── Rule-based process warnings (appended to AI dor_issues) ──────────────
    from app.models.story_process_change import StoryProcessChange
    from sqlalchemy.orm import selectinload as _sil
    pc_stmt = (
        select(StoryProcessChange)
        .where(StoryProcessChange.story_id == story_id)
        .options(_sil(StoryProcessChange.process))
    )
    process_changes = (await db.execute(pc_stmt)).scalars().all()
    if not process_changes:
        suggestion.dor_issues.append(
            "Kein Prozess verknüpft – jede Story sollte einem Prozess zugeordnet sein."
        )
    else:
        for pc in process_changes:
            if not pc.section_anchor:
                suggestion.dor_issues.append(
                    f"Prozess «{pc.process.name}»: Kein Prozessschritt (Abschnitt) angegeben."
                )
    # ─────────────────────────────────────────────────────────────────────────

    story.quality_score = suggestion.quality_score
    story.ai_suggestions = json.dumps(suggestion.model_dump(), ensure_ascii=False)
    # Auto-set dor_passed: no DoR issues AND quality_score meets threshold
    story.dor_passed = len(suggestion.dor_issues) == 0 and (suggestion.quality_score or 0) >= 80
    await db.commit()
    await db.refresh(story)

    return UserStoryRead.model_validate(story)


@router.post(
    "/user-stories/ai-suggest",
    response_model=AISuggestResponse,
    summary="Get AI improvement suggestions for a user story",
)
async def ai_suggest(
    data: AISuggestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AISuggestResponse:
    """Get AI-powered improvement suggestions and persist quality_score on the story."""
    # Resolve org for AI provider settings
    ai_settings: Optional[dict] = None
    story_obj = None
    if data.story_id:
        stmt = select(UserStory).where(UserStory.id == data.story_id)
        result = await db.execute(stmt)
        story_obj = result.scalar_one_or_none()
        if story_obj:
            ai_settings = await _get_ai_settings(story_obj.organization_id, db)

    if story_obj:
        await _check_llm_allowed(story_obj.organization_id, db)

    org_id_for_rag = story_obj.organization_id if story_obj else None
    suggestion = await get_story_suggestions(
        data, ai_settings=ai_settings, org_id=org_id_for_rag, db=db
    )

    # Persist quality_score (and full suggestion JSON) on the story when story_id given
    if story_obj:
        story_obj.quality_score = suggestion.quality_score
        story_obj.ai_suggestions = json.dumps(suggestion.model_dump(), ensure_ascii=False)
        await db.commit()
        logger.info("quality_score=%s persisted for story %s", suggestion.quality_score, data.story_id)

    return AISuggestResponse(suggestions=suggestion)


_LOCKED_STATUSES = {StoryStatus.testing, StoryStatus.done, StoryStatus.archived}


@router.post(
    "/user-stories/{story_id}/ai-test-cases",
    response_model=List[TestCaseRead],
    summary="Generate and persist AI test case suggestions",
)
async def ai_suggest_test_cases(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[TestCaseRead]:
    """Generate AI test cases and save them persistently.
    Overwrites existing AI-generated test cases if story status < 'testing'.
    """
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")

    if story.status in _LOCKED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Testfälle können nicht generiert werden — Story hat Status '{story.status.value}'.",
        )

    await _check_llm_allowed(story.organization_id, db)

    # Generate suggestions via AI
    ai_settings = await _get_ai_settings(story.organization_id, db)
    suggestions = await generate_test_case_suggestions(
        story.title,
        story.acceptance_criteria,
        ai_settings=ai_settings,
        org_id=story.organization_id,
        db=db,
    )

    # Delete existing AI-generated test cases for this story
    stmt_del = select(TestCase).where(
        TestCase.story_id == story_id,
        TestCase.is_ai_generated.is_(True),
    )
    res_del = await db.execute(stmt_del)
    for tc in res_del.scalars().all():
        await db.delete(tc)

    # Persist new AI-generated test cases
    saved: list[TestCase] = []
    for s in suggestions:
        tc = TestCase(
            organization_id=story.organization_id,
            story_id=story_id,
            created_by_id=current_user.id,
            title=s.title,
            steps=s.steps,
            expected_result=s.expected_result,
            is_ai_generated=True,
        )
        db.add(tc)
        saved.append(tc)

    await db.commit()
    for tc in saved:
        await db.refresh(tc)

    return [TestCaseRead.model_validate(tc) for tc in saved]


@router.post(
    "/user-stories/{story_id}/ai-test-case-suggestions",
    response_model=AITestCaseSuggestResponse,
    summary="Generate AI test case suggestions (preview — not persisted)",
)
async def ai_suggest_test_cases_preview(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # noqa: ARG001
) -> AITestCaseSuggestResponse:
    """Return AI test case suggestions without persisting them."""
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")

    await _check_llm_allowed(story.organization_id, db)
    ai_settings = await _get_ai_settings(story.organization_id, db)
    suggestions = await generate_test_case_suggestions(
        story.title,
        story.acceptance_criteria,
        ai_settings=ai_settings,
        org_id=story.organization_id,
        db=db,
    )
    return AITestCaseSuggestResponse(suggestions=suggestions)


@router.post(
    "/user-stories/{story_id}/ai-dod",
    response_model=AIDoDSuggestResponse,
    summary="Generate AI Definition of Done suggestions and KPIs",
)
async def ai_suggest_dod(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIDoDSuggestResponse:
    """Suggest DoD criteria and measurable KPIs for a story using AI."""
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")
    await _check_llm_allowed(story.organization_id, db)
    ai_settings = await _get_ai_settings(story.organization_id, db)
    suggestions = await generate_dod_suggestions(
        story.title,
        story.description,
        story.acceptance_criteria,
        ai_settings=ai_settings,
        org_id=story.organization_id,
        db=db,
    )
    return AIDoDSuggestResponse(suggestions=suggestions)


@router.post(
    "/user-stories/{story_id}/ai-features",
    response_model=AIFeatureSuggestResponse,
    summary="Generate AI feature suggestions for a user story",
)
async def ai_suggest_features(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIFeatureSuggestResponse:
    """Suggest concrete, implementable features (sub-functions) for a story using AI."""
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")
    await _check_llm_allowed(story.organization_id, db)
    ai_settings = await _get_ai_settings(story.organization_id, db)
    suggestions = await generate_feature_suggestions(
        story.title,
        story.description,
        story.acceptance_criteria,
        ai_settings=ai_settings,
        org_id=story.organization_id,
        db=db,
    )
    return AIFeatureSuggestResponse(suggestions=suggestions)


@router.get(
    "/user-stories/{story_id}/docs",
    response_model=Optional[StoryDocsRead],
    summary="Get saved documentation for a user story",
)
async def get_story_docs(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Optional[StoryDocsRead]:
    """Return the saved documentation, or null if none saved yet."""
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")
    if not story.generated_docs:
        return None
    data = json.loads(story.generated_docs)
    data["confluence_page_url"] = story.confluence_page_url
    data["additional_info"] = story.doc_additional_info
    data["workarounds"] = story.doc_workarounds
    return StoryDocsRead(**data)


@router.post(
    "/user-stories/{story_id}/docs/save",
    response_model=StoryDocsRead,
    summary="Save documentation for a user story, optionally publishing to Confluence",
)
async def save_story_docs(
    story_id: uuid.UUID,
    data: StoryDocsSave,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StoryDocsRead:
    """
    Persist the generated docs on the story.
    If confluence_space_key is provided, also creates a Confluence page.
    """
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")

    # Persist docs as JSON
    docs_dict = {
        "changelog_entry": data.changelog_entry,
        "pdf_outline": data.pdf_outline,
        "summary": data.summary,
        "technical_notes": data.technical_notes,
    }
    story.generated_docs = json.dumps(docs_dict, ensure_ascii=False)

    # Resolve org for Confluence credentials
    org_stmt = select(Organization).where(Organization.id == story.organization_id)
    org_result = await db.execute(org_stmt)
    org = org_result.scalar_one_or_none()

    # Publish to Confluence if requested
    confluence_url: Optional[str] = None
    if data.confluence_space_key:
        # Prefer org-level credentials, fall back to ENV
        creds = integrations_svc.get_confluence_credentials(org) if org else None
        b_url = creds[0] if creds else None
        b_user = creds[1] if creds else None
        b_token = creds[2] if creds else None
        if not confluence_service.is_configured(b_url, b_user, b_token):
            raise HTTPException(
                status_code=422,
                detail="Confluence ist nicht konfiguriert. Bitte unter Einstellungen → Confluence einrichten.",
            )
        try:
            confluence_url = await confluence_service.publish_page(
                space_key=data.confluence_space_key,
                title=story.title,
                docs=docs_dict,
                parent_page_id=data.confluence_parent_page_id,
                base_url=b_url,
                user=b_user,
                token=b_token,
            )
            story.confluence_page_url = confluence_url
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Confluence-Fehler: {exc}") from exc

    await db.commit()
    await db.refresh(story)

    # Upload docs as JSON to Nextcloud if requested
    nextcloud_path: Optional[str] = None
    if data.save_to_nextcloud and org:
        try:
            docs_content = json.dumps(docs_dict, ensure_ascii=False, indent=2).encode("utf-8")
            nextcloud_path = await nextcloud_service.upload_story_docs(
                org.slug, str(story_id), docs_content
            )
        except Exception as exc:
            logger.warning(f"Nextcloud upload failed (non-fatal): {exc}")

    return StoryDocsRead(
        **docs_dict,
        confluence_page_url=story.confluence_page_url,
        nextcloud_path=nextcloud_path,
    )


@router.post(
    "/user-stories/{story_id}/ai-split",
    response_model=StorySplitSuggestion,
    summary="AI-powered story split suggestions",
)
async def ai_split_suggestion(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StorySplitSuggestion:
    """Ask the AI to suggest how to split this story into independent sub-stories."""
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")
    ai_settings = await _get_ai_settings(story.organization_id, db)
    items = await split_story(story.title, story.description, story.acceptance_criteria, ai_settings=ai_settings)
    return StorySplitSuggestion(stories=items)


@router.post(
    "/user-stories/{story_id}/split/save",
    response_model=StorySplitResult,
    status_code=status.HTTP_201_CREATED,
    summary="Save story split — create sub-stories and optional epic",
)
async def save_story_split(
    story_id: uuid.UUID,
    data: StorySplitSave,
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StorySplitResult:
    """
    Persist the split:
    1. Optionally create an Epic
    2. Create each sub-story linked to parent + epic
    3. Mark the parent story as split
    """
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    parent = result.scalar_one_or_none()
    if parent is None:
        raise NotFoundException("User story not found")

    # Create Epic if title provided
    epic: Optional[Epic] = None
    if data.epic_title and data.epic_title.strip():
        epic = Epic(
            organization_id=org_id,
            created_by_id=current_user.id,
            title=data.epic_title.strip(),
            description=data.epic_description,
        )
        db.add(epic)
        await db.flush()  # get epic.id without committing

    # Create sub-stories
    created: list[UserStory] = []
    for item in data.stories:
        sub = UserStory(
            organization_id=org_id,
            created_by_id=current_user.id,
            title=item.title,
            description=item.description,
            acceptance_criteria=item.acceptance_criteria,
            priority=parent.priority,
            story_points=item.story_points,
            epic_id=epic.id if epic else None,
            parent_story_id=parent.id,
        )
        db.add(sub)
        created.append(sub)

    # Mark parent as split + assign epic if present
    parent.is_split = True
    if epic:
        parent.epic_id = epic.id

    await db.commit()
    for sub in created:
        await db.refresh(sub)
    if epic:
        await db.refresh(epic)

    continue_idx = max(0, min(data.continue_with_index, len(created) - 1))
    return StorySplitResult(
        epic=EpicRead.model_validate(epic) if epic else None,
        stories=[UserStoryRead.model_validate(s) for s in created],
        continue_with_id=created[continue_idx].id,
    )


@router.get(
    "/confluence/spaces",
    summary="List accessible Confluence spaces",
)
async def list_confluence_spaces(
    org_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return configured status and list of spaces (uses org-level credentials when org_id given)."""
    b_url = b_user = b_token = None
    if org_id:
        org_stmt = select(Organization).where(Organization.id == org_id)
        org_result = await db.execute(org_stmt)
        org = org_result.scalar_one_or_none()
        if org:
            creds = integrations_svc.get_confluence_credentials(org)
            if creds:
                b_url, b_user, b_token = creds
    if not confluence_service.is_configured(b_url, b_user, b_token):
        return {"configured": False, "spaces": []}
    try:
        spaces = await confluence_service.get_spaces(b_url, b_user, b_token)
        return {"configured": True, "spaces": spaces}
    except Exception as exc:
        return {"configured": True, "spaces": [], "error": str(exc)}


@router.post(
    "/user-stories/{story_id}/docs/regenerate",
    response_model=StoryDocsRead,
    summary="Regenerate and save documentation for a user story",
)
async def regenerate_story_docs(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StoryDocsRead:
    """Generate fresh docs from AI and persist them immediately."""
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")

    ai_settings = await _get_ai_settings(story.organization_id, db)
    docs = await generate_story_docs(
        DocsGenerateRequest(
            title=story.title,
            description=story.description,
            acceptance_criteria=story.acceptance_criteria,
        ),
        ai_settings=ai_settings,
    )
    docs_dict = {
        "changelog_entry": docs.changelog_entry,
        "pdf_outline": docs.pdf_outline,
        "summary": docs.summary,
        "technical_notes": docs.technical_notes,
    }
    story.generated_docs = json.dumps(docs_dict, ensure_ascii=False)
    await db.commit()
    await db.refresh(story)
    return StoryDocsRead(
        **docs_dict,
        confluence_page_url=story.confluence_page_url,
        additional_info=story.doc_additional_info,
        workarounds=story.doc_workarounds,
    )


# ---------------------------------------------------------------------------
# Confluence publish / sync
# ---------------------------------------------------------------------------

class ConfluencePublishRequest(BaseModel):
    space_key: Optional[str] = None
    org_id: uuid.UUID


class ConfluenceSyncResponse(BaseModel):
    confluence_url: str
    confluence_text: str
    heykarl_text: str
    changed: bool


@router.post(
    "/user-stories/{story_id}/docs/publish-confluence",
    response_model=StoryDocsRead,
    summary="Publish story docs to Confluence under project → story hierarchy, then link to Jira",
)
async def publish_docs_to_confluence(
    story_id: uuid.UUID,
    data: ConfluencePublishRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StoryDocsRead:
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")

    if not story.generated_docs:
        raise HTTPException(status_code=422, detail="Keine Dokumentation vorhanden. Bitte zuerst generieren.")

    docs_dict = json.loads(story.generated_docs)
    # Enrich with story fields so Confluence page contains full content
    docs_dict.setdefault("description", story.description or "")
    docs_dict.setdefault("acceptance_criteria", story.acceptance_criteria or "")
    docs_dict.setdefault("definition_of_done", story.definition_of_done or "")
    docs_dict.setdefault("doc_additional_info", story.doc_additional_info or "")
    docs_dict.setdefault("doc_workarounds", story.doc_workarounds or "")

    # Resolve org + Confluence creds
    org_stmt = select(Organization).where(Organization.id == data.org_id)
    org = (await db.execute(org_stmt)).scalar_one_or_none()
    if org is None:
        raise NotFoundException("Organisation nicht gefunden")

    creds = integrations_svc.get_confluence_credentials(org)
    if not creds or not confluence_service.is_configured(*creds):
        raise HTTPException(
            status_code=422,
            detail="Confluence ist nicht konfiguriert. Bitte unter Einstellungen → Confluence einrichten.",
        )
    b_url, b_user, b_token = creds

    conf_settings = integrations_svc.get_confluence_settings(org)
    default_parent_page_id = conf_settings.get("default_parent_page_id") or None

    # Resolve space key: explicit > org default > derived from parent page
    space_key = (data.space_key or "").strip()
    if not space_key:
        space_key = conf_settings.get("default_space_key", "")
    if not space_key and default_parent_page_id:
        try:
            space_key = await confluence_service.get_space_key_for_page(
                default_parent_page_id, b_url, b_user, b_token
            )
        except Exception:
            pass
    if not space_key:
        raise HTTPException(status_code=422, detail="Kein Confluence Space-Key angegeben.")

    # Resolve project name
    project_name: str | None = None
    if story.project_id:
        proj_stmt = select(Project).where(Project.id == story.project_id)
        proj = (await db.execute(proj_stmt)).scalar_one_or_none()
        if proj:
            project_name = proj.name

    try:
        confluence_url = await confluence_service.publish_story_page(
            space_key=space_key,
            story_title=story.title,
            docs=docs_dict,
            project_name=project_name,
            base_url=b_url,
            user=b_user,
            token=b_token,
            existing_page_url=story.confluence_page_url,
            default_parent_page_id=default_parent_page_id,
        )
        story.confluence_page_url = confluence_url
    except Exception as exc:
        import httpx as _httpx
        detail = str(exc)
        if isinstance(exc, _httpx.HTTPStatusError):
            try:
                body = exc.response.json()
                detail = body.get("message") or body.get("detail") or (body.get("errorMessages") or [detail])[0]
            except Exception:
                detail = f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        raise HTTPException(status_code=502, detail=f"Confluence-Fehler: {detail}") from exc

    # Link Confluence page to Jira ticket if we have credentials + ticket key
    if story.jira_ticket_key:
        jira_creds = integrations_svc.get_jira_settings(org)
        jira_token = integrations_svc.get_jira_token(org)
        if jira_creds.get("base_url") and jira_creds.get("user") and jira_token:
            try:
                await jira_service.add_remote_link_basic(
                    base_url=jira_creds["base_url"],
                    user=jira_creds["user"],
                    api_token=jira_token,
                    issue_key=story.jira_ticket_key,
                    link_url=confluence_url,
                    link_title=f"Confluence: {story.title}",
                )
            except Exception as exc:
                logger.warning("Jira remote link failed (non-fatal): %s", exc)

    await db.commit()
    await db.refresh(story)

    return StoryDocsRead(
        **docs_dict,
        confluence_page_url=story.confluence_page_url,
        additional_info=story.doc_additional_info,
        workarounds=story.doc_workarounds,
    )


@router.get(
    "/user-stories/{story_id}/docs/confluence-sync",
    response_model=ConfluenceSyncResponse,
    summary="Compare HeyKarl docs with current Confluence page content",
)
async def confluence_sync_preview(
    story_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConfluenceSyncResponse:
    stmt = select(UserStory).where(UserStory.id == story_id)
    story = (await db.execute(stmt)).scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")
    if not story.confluence_page_url:
        raise HTTPException(status_code=422, detail="Kein Confluence-Link vorhanden.")
    if not story.generated_docs:
        raise HTTPException(status_code=422, detail="Keine Dokumentation vorhanden.")

    org_stmt = select(Organization).where(Organization.id == org_id)
    org = (await db.execute(org_stmt)).scalar_one_or_none()
    if org is None:
        raise NotFoundException("Organisation nicht gefunden")

    creds = integrations_svc.get_confluence_credentials(org)
    if not creds:
        raise HTTPException(status_code=422, detail="Confluence ist nicht konfiguriert.")
    b_url, b_user, b_token = creds

    # Extract page ID from the stored Confluence URL
    # URL pattern: {base}/wiki/spaces/{SPACE}/pages/{id}/...
    import re as _re
    page_id_match = _re.search(r"/pages/(\d+)", story.confluence_page_url)
    if not page_id_match:
        raise HTTPException(status_code=422, detail="Confluence-Seiten-ID konnte nicht ermittelt werden.")
    page_id = page_id_match.group(1)

    try:
        confluence_text = await confluence_service.get_page_content_text(page_id, b_url, b_user, b_token)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Confluence-Fehler: {exc}") from exc

    docs_dict = json.loads(story.generated_docs)
    heykarl_text = (
        f"Zusammenfassung: {docs_dict.get('summary', '')}\n\n"
        f"Changelog: {docs_dict.get('changelog_entry', '')}\n\n"
        f"Technische Hinweise: {docs_dict.get('technical_notes', '')}\n\n"
        f"Gliederung: {', '.join(docs_dict.get('pdf_outline', []))}"
    )

    changed = confluence_text.strip() != heykarl_text.strip()
    return ConfluenceSyncResponse(
        confluence_url=story.confluence_page_url,
        confluence_text=confluence_text,
        heykarl_text=heykarl_text,
        changed=changed,
    )


@router.post(
    "/user-stories/{story_id}/docs/pdf",
    tags=["Documentation"],
    summary="Generate PDF for a user story and upload to Nextcloud",
)
async def generate_and_upload_pdf(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Generate a PDF for the user story using the org's PDF settings,
    then upload it to Nextcloud under Organizations/{org_slug}/Dokumentation/.
    Returns {"ok": True, "path": "<nextcloud path>"}.
    """
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")

    # Resolve org
    org_stmt = select(Organization).where(Organization.id == story.organization_id)
    org_result = await db.execute(org_stmt)
    org = org_result.scalar_one_or_none()
    if org is None:
        raise NotFoundException("Organisation nicht gefunden")

    # Load PDF settings (fall back to defaults)
    settings_result = await db.execute(
        select(PdfSettings).where(PdfSettings.organization_id == story.organization_id)
    )
    pdf_settings = settings_result.scalar_one_or_none()
    if pdf_settings is None:
        pdf_settings = SimpleNamespace(
            company_name=None, page_format="a4", language="de",
            header_text=None, footer_text=None,
            letterhead_filename=None, logo_filename=None,
        )

    # Load related data
    tc_result = await db.execute(select(TestCase).where(TestCase.story_id == story.id))
    test_cases = tc_result.scalars().all()

    feat_result = await db.execute(select(Feature).where(Feature.story_id == story.id))
    features = feat_result.scalars().all()

    # Generate PDF → returns cache filename
    filename = await pdf_service.generate_and_cache(story, pdf_settings, test_cases, features)

    # Read cached PDF bytes
    cfg = get_settings()
    pdf_path = Path(cfg.PDF_CACHE_PATH) / filename
    pdf_bytes = pdf_path.read_bytes()

    # Sanitise story title for filename
    safe_title = re.sub(r"[^\w\-äöüÄÖÜß ]", "", story.title).strip().replace(" ", "_")
    safe_title = safe_title[:80] or str(story_id)
    pdf_filename = f"{safe_title}.pdf"

    dest_path = f"Organizations/{org.slug}/{pdf_filename}"
    auth = (cfg.NEXTCLOUD_ADMIN_USER, cfg.NEXTCLOUD_ADMIN_APP_PASSWORD)

    dav_base = f"{cfg.NEXTCLOUD_INTERNAL_URL}/remote.php/dav/files/{cfg.NEXTCLOUD_ADMIN_USER}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Ensure org folder exists
        for segment in ["Organizations", f"Organizations/{org.slug}"]:
            r = await client.request("MKCOL", f"{dav_base}/{segment}/", auth=auth)
            if r.status_code not in (201, 405):
                logger.warning(f"MKCOL /{segment}/ → {r.status_code}")

        # Upload PDF
        resp = await client.put(
            f"{dav_base}/{dest_path}", content=pdf_bytes, auth=auth,
            headers={"Content-Type": "application/pdf"},
        )
        resp.raise_for_status()

    # Persist Nextcloud path in story's generated_docs
    docs: dict = {}
    if story.generated_docs:
        try:
            docs = json.loads(story.generated_docs)
        except (json.JSONDecodeError, TypeError):
            docs = {}
    docs["nextcloud_path"] = dest_path
    story.generated_docs = json.dumps(docs, ensure_ascii=False)
    await db.commit()

    logger.info(f"PDF uploaded to Nextcloud: {dest_path}")
    return {"ok": True, "path": dest_path, "filename": pdf_filename}


@router.post(
    "/user-stories/ai-docs",
    response_model=DocsGenerateResponse,
    summary="Generate documentation for a user story",
)
async def ai_generate_docs(
    data: DocsGenerateRequest,
    current_user: User = Depends(get_current_user),
) -> DocsGenerateResponse:
    """Generate changelog, PDF outline, and summary for a user story."""
    return await generate_story_docs(data)
