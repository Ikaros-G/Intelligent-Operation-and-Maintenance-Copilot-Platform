"""Knowledge-base background task API contracts."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class TaskState(StrEnum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    RETRY = "RETRY"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class TaskQueuedResponse(BaseModel):
    task_id: str
    state: TaskState = TaskState.PENDING
    status_url: str
    filename: str


class TaskStatusResponse(BaseModel):
    task_id: str
    state: TaskState
    result: dict[str, Any] | None = None
    progress: dict[str, Any] | None = None
    error: str | None = None

    @classmethod
    def from_async_result(cls, task_id: str, async_result: Any) -> "TaskStatusResponse":
        try:
            state = TaskState(str(async_result.state))
        except ValueError:
            state = TaskState.PENDING
        result = async_result.result if state is TaskState.SUCCESS else None
        progress = async_result.info if state in {TaskState.STARTED, TaskState.RETRY} and isinstance(async_result.info, dict) else None
        error = "知识库任务执行失败" if state is TaskState.FAILURE else None
        return cls(task_id=task_id, state=state, result=result, progress=progress, error=error)
