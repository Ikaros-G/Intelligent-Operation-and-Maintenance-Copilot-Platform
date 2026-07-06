"""Typed contracts used for communication between AIOps agents."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentRole(StrEnum):
    ORCHESTRATOR = "orchestrator"
    PLANNER = "planner"
    DIAGNOSIS = "diagnosis"
    REPORT = "report"


class MessageType(StrEnum):
    TASK_REQUEST = "task_request"
    PLAN_CREATED = "plan_created"
    EXECUTION_REQUEST = "execution_request"
    EVIDENCE_COLLECTED = "evidence_collected"
    PLAN_UPDATED = "plan_updated"
    REPORT_REQUEST = "report_request"
    REPORT_CREATED = "report_created"
    ERROR = "error"


class AgentMessage(BaseModel):
    """Serializable envelope for every agent-to-agent handoff."""

    message_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    sender: AgentRole
    recipient: AgentRole
    message_type: MessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        correlation_id: str,
        sender: AgentRole,
        recipient: AgentRole,
        message_type: MessageType,
        payload: dict[str, Any],
    ) -> "AgentMessage":
        return cls(
            message_id=str(uuid4()),
            correlation_id=correlation_id,
            sender=sender,
            recipient=recipient,
            message_type=message_type,
            payload=payload,
            created_at=datetime.now(UTC),
        )


class PlanStep(BaseModel):
    step_id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    suggested_tools: list[str] = Field(default_factory=list)


class DiagnosisPlan(BaseModel):
    rationale: str = ""
    steps: list[PlanStep] = Field(min_length=1)


class ExecutionEvidence(BaseModel):
    step_id: str
    objective: str
    summary: str
    success: bool = True


class DiagnosticReport(BaseModel):
    markdown: str = Field(min_length=1, description="基于诊断证据生成的 Markdown 故障报告")
