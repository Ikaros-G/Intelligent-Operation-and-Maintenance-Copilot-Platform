"""Asynchronous document parsing, chunking, embedding, and indexing tasks."""

from pathlib import Path
from typing import Any

from celery.utils.log import get_task_logger

from .celery_app import celery_app

logger = get_task_logger(__name__)
UPLOAD_DIR = Path("uploads")


def resolve_upload_path(file_path: str, upload_dir: Path = UPLOAD_DIR) -> Path:
    root = upload_dir.resolve()
    path = Path(file_path).resolve()
    if root not in path.parents:
        raise ValueError("任务文件必须位于上传目录")
    if not path.is_file():
        raise ValueError("上传文件不存在")
    return path


@celery_app.task(bind=True, name="knowledge.index_document", autoretry_for=(ConnectionError, TimeoutError), retry_backoff=True, retry_jitter=True, max_retries=3)
def index_document_task(self: Any, file_path: str) -> dict[str, Any]:
    path = resolve_upload_path(file_path)
    self.update_state(state="STARTED", meta={"stage": "indexing", "filename": path.name})
    from app.services.vector_index_service import vector_index_service

    vector_index_service.index_single_file(str(path))
    logger.info(
        "knowledge_document_indexed",
        extra={"document_name": path.name, "task_id": self.request.id},
    )
    return {"filename": path.name, "status": "indexed"}
