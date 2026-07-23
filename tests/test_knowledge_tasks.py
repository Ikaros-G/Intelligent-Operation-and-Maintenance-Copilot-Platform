from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.file import _resolve_index_directory
from app.models.task import TaskState, TaskStatusResponse
from app.tasks.knowledge_tasks import resolve_upload_path


class FakeAsyncResult:
    def __init__(self, state, result=None, info=None):
        self.state = state
        self.result = result
        self.info = info


def test_task_status_maps_success_result():
    status = TaskStatusResponse.from_async_result(
        "task-1", FakeAsyncResult("SUCCESS", result={"filename": "runbook.md", "chunks": 4})
    )

    assert status.task_id == "task-1"
    assert status.state is TaskState.SUCCESS
    assert status.result == {"filename": "runbook.md", "chunks": 4}
    assert status.error is None


def test_task_status_hides_internal_failure_details():
    status = TaskStatusResponse.from_async_result(
        "task-2", FakeAsyncResult("FAILURE", result=RuntimeError("redis://secret@host"))
    )

    assert status.state is TaskState.FAILURE
    assert status.error == "知识库任务执行失败"


def test_resolve_upload_path_rejects_paths_outside_upload_directory(tmp_path: Path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    valid_file = upload_dir / "guide.md"
    valid_file.write_text("hello", encoding="utf-8")

    assert resolve_upload_path(str(valid_file), upload_dir) == valid_file.resolve()

    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("secret", encoding="utf-8")
    with pytest.raises(ValueError, match="上传目录"):
        resolve_upload_path(str(outside_file), upload_dir)


def test_resolve_index_directory_defaults_to_upload_directory(tmp_path: Path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    assert _resolve_index_directory(None, upload_dir) == upload_dir.resolve()


def test_resolve_index_directory_allows_upload_subdirectories(tmp_path: Path):
    upload_dir = tmp_path / "uploads"
    nested_dir = upload_dir / "runbooks"
    nested_dir.mkdir(parents=True)

    assert _resolve_index_directory(str(nested_dir), upload_dir) == nested_dir.resolve()


def test_resolve_index_directory_rejects_paths_outside_upload_directory(tmp_path: Path):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    with pytest.raises(HTTPException, match="上传目录"):
        _resolve_index_directory(str(outside_dir), upload_dir)
