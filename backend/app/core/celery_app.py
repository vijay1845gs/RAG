"""
Celery application factory for async document ingestion pipeline.

Design decisions:
- Broker: Redis (redis://localhost:6379/0)  — task queuing only
- Result backend: rpc://                   — avoids Redis memory bloat from stale task metadata
- Pool: solo                               — required for Windows development
- State storage: Supabase DB              — single source of truth for processing_status / progress

Production migration:
  Switch pool to 'prefork' when deploying on Linux/WSL2/Docker.
  Change CELERY_RESULT_BACKEND to 'rpc://' or 'db+postgresql://...' as needed.
"""

import logging
from celery import Celery
from celery.signals import task_failure, task_success, worker_ready

logger = logging.getLogger(__name__)

# ─── Import settings lazily to avoid circular imports ────────────────────────
def _get_settings():
    from app.core.config import settings
    return settings


def create_celery_app() -> Celery:
    """Build and configure the Celery application."""
    s = _get_settings()

    app = Celery(
        "rag_worker",
        broker=s.CELERY_BROKER_URL,
        backend=s.CELERY_RESULT_BACKEND,
        include=["app.tasks.document_tasks"],
    )

    app.conf.update(
        # Serialization
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        # Reliability — at-least-once with manual ack
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        # Retry defaults (tasks override per-call)
        task_max_retries=s.CELERY_TASK_MAX_RETRIES,
        # Timezone
        timezone="UTC",
        enable_utc=True,
        # Windows compatibility — solo pool executes tasks in-process
        # Switch to 'prefork' on Linux/Docker production
        worker_pool="solo",
        # Beat disabled (no scheduled tasks needed yet)
        beat_schedule={},
        # Result expiry — rpc:// results are short-lived anyway
        result_expires=3600,
        # Task routing — single queue for now, extend with priority queues later
        task_default_queue="document_processing",
        task_queues={
            "document_processing": {
                "exchange": "document_processing",
                "routing_key": "document_processing",
            }
        },
    )

    return app


# Module-level singleton — imported by tasks and routes
celery_app = create_celery_app()


# ─── Lifecycle signal handlers ────────────────────────────────────────────────

@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    logger.info("Celery worker ready. broker=%s backend=%s", 
                 celery_app.conf.broker_url, celery_app.conf.result_backend)


@task_success.connect
def on_task_success(sender, result, **kwargs):
    logger.info("Task completed successfully. task=%s", sender.name)


@task_failure.connect
def on_task_failure(sender, task_id, exception, traceback, einfo, **kwargs):
    logger.error(
        "Task failed. task=%s task_id=%s error=%s",
        sender.name, task_id, str(exception),
    )


__all__ = ["celery_app"]
