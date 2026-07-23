"""AIOps diagnosis endpoints."""

import json

from fastapi import APIRouter, Header, HTTPException
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from app.agent.aiops.security import OperatorRole
from app.api.streams import stream_response
from app.config import config
from app.models.aiops import AIOpsRequest, ApprovalRequest
from app.services.aiops_service import aiops_service
from app.services.resumable_stream_service import resumable_stream_service


router = APIRouter()


@router.post("/aiops")
async def diagnose_stream(
    request: AIOpsRequest,
    x_operator_role: str = Header(default="viewer"),
    x_operator_key: str | None = Header(default=None),
):
    """Start a detached diagnosis and subscribe to its replayable SSE events."""
    session_id = request.session_id or "default"
    operator_role = _authorize_role(x_operator_role, x_operator_key)
    logger.info("[会话 {}] 收到 AIOps 流式诊断请求", session_id)

    async def event_generator():
        try:
            async for event in aiops_service.diagnose(
                session_id=session_id,
                operator_role=operator_role.value,
            ):
                yield event
                if event.get("type") in {"complete", "error"}:
                    break
            logger.info("[会话 {}] AIOps 诊断后台任务完成", session_id)
        except Exception as exc:
            logger.exception("[会话 {}] AIOps 诊断后台任务异常: {}", session_id, type(exc).__name__)
            yield {
                "type": "error",
                "stage": "exception",
                "message": "诊断服务暂时不可用",
            }

    stream_id = await resumable_stream_service.start("aiops", session_id, event_generator)
    return stream_response(stream_id)


@router.post("/aiops/{session_id}/approval")
async def resume_diagnosis(
    session_id: str,
    approval: ApprovalRequest,
    x_operator_key: str | None = Header(default=None),
):
    _authorize_role("admin", x_operator_key)

    async def event_generator():
        async for event in aiops_service.resume(session_id, approval.model_dump()):
            yield {"event": "message", "data": json.dumps(event, ensure_ascii=False)}

    return EventSourceResponse(event_generator())


def _authorize_role(raw_role: str, operator_key: str | None) -> OperatorRole:
    try:
        role = OperatorRole(raw_role.lower())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="无效的操作员角色") from exc
    if role is OperatorRole.VIEWER:
        return role
    if not config.ops_api_key:
        raise HTTPException(status_code=503, detail="高权限操作尚未配置")
    if operator_key != config.ops_api_key:
        raise HTTPException(status_code=403, detail="操作员凭据无效")
    return role
