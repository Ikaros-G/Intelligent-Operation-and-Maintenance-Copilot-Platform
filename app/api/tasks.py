"""Background task status endpoints."""

from celery.result import AsyncResult
from fastapi import APIRouter

from app.models.task import TaskStatusResponse
from app.tasks.celery_app import celery_app

router = APIRouter()


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    return TaskStatusResponse.from_async_result(task_id, AsyncResult(task_id, app=celery_app))
