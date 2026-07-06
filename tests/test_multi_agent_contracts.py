from uuid import UUID

import pytest
from pydantic import ValidationError

from app.agent.aiops.contracts import (
    AgentMessage,
    AgentRole,
    DiagnosisPlan,
    MessageType,
    PlanStep,
)


def test_agent_message_factory_creates_traceable_handoff():
    message = AgentMessage.create(
        correlation_id="session-42",
        sender=AgentRole.PLANNER,
        recipient=AgentRole.DIAGNOSIS,
        message_type=MessageType.EXECUTION_REQUEST,
        payload={"step_id": "step-1"},
    )

    UUID(message.message_id)
    assert message.correlation_id == "session-42"
    assert message.sender is AgentRole.PLANNER
    assert message.recipient is AgentRole.DIAGNOSIS
    assert message.payload == {"step_id": "step-1"}
    assert message.created_at.tzinfo is not None


def test_agent_message_rejects_empty_correlation_id():
    with pytest.raises(ValidationError):
        AgentMessage.create(
            correlation_id="",
            sender=AgentRole.PLANNER,
            recipient=AgentRole.DIAGNOSIS,
            message_type=MessageType.EXECUTION_REQUEST,
            payload={},
        )


def test_diagnosis_plan_requires_at_least_one_executable_step():
    with pytest.raises(ValidationError):
        DiagnosisPlan(steps=[])

    plan = DiagnosisPlan(
        rationale="先确认告警，再采集证据",
        steps=[PlanStep(step_id="step-1", objective="查询当前活跃告警")],
    )

    assert plan.steps[0].step_id == "step-1"
    assert plan.steps[0].objective == "查询当前活跃告警"
