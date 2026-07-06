"""Diagnosis Agent: executes one planned step and returns evidence."""

from typing import Any

from .contracts import AgentMessage, AgentRole, ExecutionEvidence, MessageType
from .state import PlanExecuteState


class DiagnosisAgent:
    role = AgentRole.DIAGNOSIS

    async def execute(self, state: PlanExecuteState) -> dict[str, Any]:
        # 工具/MCP 依赖只在真正执行诊断时加载。
        from .executor import executor as execute_legacy_step

        plan = state.get("plan", [])
        if not plan:
            return {"next_agent": "report"}

        step = plan[0]
        legacy_state = dict(state)
        legacy_state["plan"] = [item["objective"] for item in plan]
        output = await execute_legacy_step(legacy_state)  # type: ignore[arg-type]
        result = str(output.get("past_steps", [(step["objective"], "未获得执行结果")])[-1][1])
        evidence = ExecutionEvidence(
            step_id=step["step_id"],
            objective=step["objective"],
            summary=result,
            success=not result.startswith("执行失败:"),
        )
        message = AgentMessage.create(
            correlation_id=state.get("correlation_id", "default"),
            sender=self.role,
            recipient=AgentRole.PLANNER,
            message_type=MessageType.EVIDENCE_COLLECTED,
            payload=evidence.model_dump(),
        )
        return {
            "plan": plan[1:],
            "past_steps": [(step["objective"], result)],
            "evidence": [evidence.model_dump()],
            "agent_messages": [message.model_dump(mode="json")],
            "next_agent": "planner",
            "approval_granted": False,
            "approved_tools": [],
        }
