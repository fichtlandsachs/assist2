from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery = Celery(
    "assist2",
    broker=settings.REDIS_URL.replace("/0", "/1"),
    backend=settings.REDIS_URL.replace("/0", "/2"),
    include=[
        "app.tasks.mail_sync",
        "app.tasks.calendar_sync",
        "app.tasks.agent_tasks",
        "app.tasks.pdf_tasks",
        "app.tasks.sync_dispatcher",
        "app.tasks.rag_tasks",
    ]
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery.conf.beat_schedule = {
    "dispatch-mail-sync": {
        "task": "sync_dispatcher.dispatch_mail_sync",
        "schedule": 60.0,
    },
    "dispatch-calendar-sync": {
        "task": "sync_dispatcher.dispatch_calendar_sync",
        "schedule": 60.0,
    },
    "dispatch-rag-index": {
        "task": "sync_dispatcher.dispatch_rag_index",
        "schedule": crontab(hour=2, minute=0),  # daily at 02:00 UTC
    },
}
