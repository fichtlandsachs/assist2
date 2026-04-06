"""Org-level stats endpoint for dashboard: status distributions + velocity."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.epic import Epic
from app.models.feature import Feature
from app.models.test_case import TestCase
from app.models.user import User
from app.models.user_story import UserStory

router = APIRouter()


@router.get("/orgs/{org_id}/stats")
async def get_org_stats(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)

    # ── Status distributions ─────────────────────────────────────────────────

    async def status_counts(model, status_col="status"):
        col = getattr(model, status_col)
        rows = (await db.execute(
            select(col, func.count().label("n"))
            .where(model.organization_id == org_id)
            .group_by(col)
        )).all()
        return {str(r[0]): r[1] for r in rows}

    stories_dist = await status_counts(UserStory)
    epics_dist = await status_counts(Epic)
    features_dist = await status_counts(Feature)
    test_cases_dist = await status_counts(TestCase, status_col="result")

    # ── Story point totals ───────────────────────────────────────────────────
    sp_rows = (await db.execute(
        select(
            func.sum(UserStory.story_points).label("total"),
            func.sum(
                UserStory.story_points
            ).filter(UserStory.status == "done").label("done"),
        ).where(UserStory.organization_id == org_id)
    )).one()
    sp_total = sp_rows.total or 0
    sp_done = sp_rows.done or 0

    # ── Weekly velocity (last 8 weeks) ───────────────────────────────────────
    # Velocity = story points of stories marked "done" in each calendar week
    # We use updated_at as proxy for completion date.
    velocity = []
    for weeks_ago in range(7, -1, -1):
        week_start = (now - timedelta(weeks=weeks_ago)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # align to Monday
        week_start -= timedelta(days=week_start.weekday())
        week_end = week_start + timedelta(days=7)

        row = (await db.execute(
            select(
                func.count().label("count"),
                func.coalesce(func.sum(UserStory.story_points), 0).label("points"),
            ).where(
                UserStory.organization_id == org_id,
                UserStory.status == "done",
                UserStory.updated_at >= week_start,
                UserStory.updated_at < week_end,
            )
        )).one()

        iso_week = week_start.isocalendar()
        velocity.append({
            "week": f"KW {iso_week[1]}",
            "count": row.count,
            "points": int(row.points),
        })

    return {
        "stories": stories_dist,
        "epics": epics_dist,
        "features": features_dist,
        "test_cases": test_cases_dist,
        "story_points_total": sp_total,
        "story_points_done": sp_done,
        "velocity": velocity,
    }
