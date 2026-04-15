"""Jira ↔ UserStory consistency sync."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from dateutil import parser as dateutil_parser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user_story import UserStory
from app.services.jira_service import JiraService
from app.services.org_integrations_service import get_jira_settings, get_jira_token

logger = logging.getLogger(__name__)
jira_service = JiraService()


class JiraSyncService:
    async def sync_story_from_jira(
        self, story: UserStory, db: AsyncSession
    ) -> bool:
        """Fetch fresh Jira data for story.jira_ticket_key and update jira_* fields.

        Returns True if any field changed, False if skipped or unchanged.
        """
        if not story.jira_ticket_key:
            return False

        # Org laden
        result = await db.execute(
            select(Organization).where(Organization.id == story.organization_id)
        )
        org = result.scalar_one_or_none()
        if org is None:
            return False

        # Jira-Credentials prüfen
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

        if not data:
            # Ticket existiert nicht mehr in Jira
            story.jira_status = "deleted"
            story.jira_last_synced_at = datetime.now(tz=timezone.utc)
            await db.commit()
            return True

        # Felder mappen
        story.jira_creator = data.get("creator") or None
        story.jira_reporter = data.get("reporter") or None
        story.jira_status = data.get("status") or None

        raw_created = data.get("created")
        story.jira_created_at = (
            dateutil_parser.parse(raw_created) if raw_created else None
        )
        raw_updated = data.get("updated")
        story.jira_updated_at = (
            dateutil_parser.parse(raw_updated) if raw_updated else None
        )

        links = data.get("issue_links", [])
        story.jira_linked_issue_keys = json.dumps(links)

        story.jira_last_synced_at = datetime.now(tz=timezone.utc)

        await db.commit()
        return True
