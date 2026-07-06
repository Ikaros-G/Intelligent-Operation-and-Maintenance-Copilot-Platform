"""Celery application configured with Redis broker and result backend."""

from celery import Celery

from app.config import config

celery_app = Celery(
    "aiops_copilot",
    broker=config.celery_broker_url,
    backend=config.celery_result_backend,
    include=["app.tasks.knowledge_tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=config.celery_task_time_limit,
    task_soft_time_limit=max(1, config.celery_task_time_limit - 30),
    broker_transport_options={"visibility_timeout": config.celery_task_time_limit + 60},
    result_backend_transport_options={"global_keyprefix": "aiops:celery:", "retry_policy": {"timeout": 5.0}},
    result_expires=86400,
)
