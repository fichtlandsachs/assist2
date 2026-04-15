"""Jira ↔ UserStory consistency sync."""
from __future__ import annotations

import json
import logging
import uuid as _uuid
from datetime import datetime, timezone

from dateutil import parser as dateutil_parser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user_story import UserStory
from app.services.atlassian_token import atlassian_token_store
from app.services.jira_service import JiraService
from app.services.org_integrations_service import get_jira_settings, get_jira_token

logger = logging.getLogger(__name__)
jira_service = JiraService()

JIRA_STATUS_DELETED = "deleted"


def _parse_jira_dt(raw: str | None) -> datetime | None:
    """Parse a Jira ISO8601 timestamp to a UTC-aware datetime, or None on failure."""
    if not raw:
        return None
    try:
        dt = dateutil_parser.parse(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        logger.warning("Could not parse Jira timestamp: %r", raw)
        return None


class JiraSyncService:
    async def sync_story_from_jira(
        self,
        story: UserStory,
        db: AsyncSession,
        user_id: _uuid.UUID | None = None,
    ) -> bool:
        """Fetch fresh Jira data for story.jira_ticket_key and update jira_* fields.

        When user_id is provided, the user's personal Atlassian OAuth token is
        tried first (auto-refreshed if near expiry). Falls back to org-level
        Basic Auth credentials if no personal token is available.

        Returns True if Jira data was fetched and fields were written,
        False if skipped (no ticket key, no credentials, fetch error).
        """
        if not story.jira_ticket_key:
            return False

        # Persönlichen OAuth-Token des Users versuchen (nur bei manuellem Sync)
        if user_id is not None:
            try:
                access_token = await atlassian_token_store.get_valid_token(user_id)
                if access_token:
                    token_data = await atlassian_token_store.get(user_id)
                    cloud_id = token_data["cloud_id"] if token_data else None
                    if cloud_id:
                        try:
                            data = await jira_service.get_ticket(
                                access_token=access_token,
                                cloud_id=cloud_id,
                                key=story.jira_ticket_key,
                            )
                            return await self._apply_jira_data(story, db, data)
                        except Exception as exc:
                            logger.debug(
                                "Personal OAuth sync failed for %s, falling back to org: %s",
                                story.jira_ticket_key,
                                exc,
                            )
            except Exception as exc:
                logger.debug("Could not load personal Atlassian token: %s", exc)

        # Org laden
        result = await db.execute(
            select(Organization).where(Organization.id == story.organization_id)
        )
        org = result.scalar_one_or_none()
        if org is None:
            return False

        # Org-Credentials prüfen (Basic Auth Fallback)
        api_token = get_jira_token(org)
        if not api_token:
            return False

        settings = get_jira_settings(org)
        base_url = settings.get("base_url", "")
        user = settings.get("user", "")
        if not base_url or not user:
            return False

        # Jira-Daten abrufen
        try:
            data = await jira_service.get_ticket_basic(
                base_url=base_url,
                user=user,
                api_token=api_token,
                key=story.jira_ticket_key,
            )
        except Exception as exc:
            logger.warning("Jira sync failed for %s: %s", story.jira_ticket_key, exc)
            return False

        return await self._apply_jira_data(story, db, data)

    async def _apply_jira_data(
        self, story: UserStory, db: AsyncSession, data: dict
    ) -> bool:
        """Write Jira API response onto story fields and commit. Returns True."""
        if not data:
            # Ticket existiert nicht mehr in Jira
            story.jira_status = JIRA_STATUS_DELETED
            story.jira_last_synced_at = datetime.now(tz=timezone.utc)
            await db.commit()
            return True

        # Felder mappen
        story.jira_creator = data.get("creator") or None
        story.jira_reporter = data.get("reporter") or None
        story.jira_status = data.get("status") or None

        story.jira_created_at = _parse_jira_dt(data.get("created"))
        story.jira_updated_at = _parse_jira_dt(data.get("updated"))

        links = data.get("issue_links", [])
        story.jira_linked_issue_keys = json.dumps(links)

        story.jira_last_synced_at = datetime.now(tz=timezone.utc)

        await db.commit()
        return True
