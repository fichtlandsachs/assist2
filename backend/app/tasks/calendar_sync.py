from app.celery_app import celery


@celery.task(name="calendar_sync.sync_calendar")
def sync_calendar_task(connection_id: str, org_id: str):
    """Sync calendar events for a calendar connection."""
    # Implemented in Wave 5
    return {"status": "ok", "connection_id": connection_id}
