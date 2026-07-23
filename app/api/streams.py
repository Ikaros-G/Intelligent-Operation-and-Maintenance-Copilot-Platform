"""Replay and resume detached SSE streams."""

import json
import re

from fastapi import APIRouter, Header, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from app.services.resumable_stream_service import resumable_stream_service


router = APIRouter()
CURSOR_PATTERN = re.compile(r"^\d+-\d+$")


def stream_response(stream_id: str, after: str = "0-0") -> EventSourceResponse:
    async def event_generator():
        async for event_id, event in resumable_stream_service.events(stream_id, after=after):
            yield {
                "id": event_id,
                "event": "message",
                "data": json.dumps(event, ensure_ascii=False),
            }

    return EventSourceResponse(
        event_generator(),
        ping=10,
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-Stream-ID": stream_id,
        },
    )


@router.get("/streams/{stream_id}")
async def resume_stream(
    stream_id: str,
    after: str = Query(default="0-0"),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    metadata = await resumable_stream_service.metadata(stream_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="流任务不存在或已过期")
    cursor = last_event_id or after or "0-0"
    if not CURSOR_PATTERN.fullmatch(cursor):
        raise HTTPException(status_code=422, detail="无效的事件游标")
    return stream_response(stream_id, cursor)


@router.get("/streams/{stream_id}/status")
async def stream_status(stream_id: str):
    metadata = await resumable_stream_service.metadata(stream_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="流任务不存在或已过期")
    return metadata
