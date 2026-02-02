"""
Celery Application Configuration

Configures Celery with Redis broker and result backend.
Defines task queues and routing.
"""

import os

from celery import Celery
from celery.schedules import crontab

# Broker and backend URLs
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

app = Celery(
    "safeharbor",
    broker=REDIS_URL,
    backend=RESULT_BACKEND,
)

app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task behavior
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Result expiry
    result_expires=86400,  # 24 hours

    # Routing
    task_routes={
        "workers.tasks.sync_tasks.*": {"queue": "sync"},
        "workers.tasks.calculation_tasks.*": {"queue": "calculations"},
        "workers.tasks.compliance_tasks.*": {"queue": "compliance"},
        "workers.tasks.notification_tasks.*": {"queue": "notifications"},
    },

    # Default queue
    task_default_queue="default",

    # Concurrency
    worker_concurrency=4,

    # Rate limits
    task_annotations={
        "workers.tasks.sync_tasks.sync_integration": {
            "rate_limit": "10/m",
        },
    },
)

# Beat schedule for periodic tasks
app.conf.beat_schedule = {
    # Payroll sync every hour
    "sync-payroll-hourly": {
        "task": "workers.tasks.sync_tasks.sync_all_payroll",
        "schedule": crontab(minute=0),  # Every hour
        "options": {"queue": "sync"},
    },

    # POS sync every 15 minutes
    "sync-pos-frequent": {
        "task": "workers.tasks.sync_tasks.sync_all_pos",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "sync"},
    },

    # Timekeeping sync every 30 minutes
    "sync-timekeeping": {
        "task": "workers.tasks.sync_tasks.sync_all_timekeeping",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "sync"},
    },

    # Compliance vault maintenance daily at 3 AM UTC
    "vault-maintenance": {
        "task": "workers.tasks.compliance_tasks.vault_maintenance",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "compliance"},
    },

    # Stale integration check daily at 6 AM UTC
    "check-stale-integrations": {
        "task": "workers.tasks.sync_tasks.check_stale_integrations",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": "sync"},
    },

    # Phase-out risk check weekly on Monday
    "weekly-phase-out-check": {
        "task": "workers.tasks.calculation_tasks.check_phase_out_risks",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),
        "options": {"queue": "calculations"},
    },
}

# Initialize Sentry for error monitoring in workers
_sentry_dsn = os.getenv("SENTRY_DSN", "")
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=os.getenv("ENVIRONMENT", "development"),
        release=f"safeharbor-worker@{os.getenv('APP_VERSION', '0.1.0')}",
        traces_sample_rate=0.1,
        integrations=[CeleryIntegration()],
    )

# Auto-discover tasks
app.autodiscover_tasks(["workers.tasks"])
