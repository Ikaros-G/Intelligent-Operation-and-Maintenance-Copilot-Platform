"""Planner Agent: creates and revises diagnostic plans."""

from typing import Any, Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_qwq import ChatQwen
from loguru import logger
from pydantic import BaseModel, Field

from app.config import config

from .contracts import AgentMessage, AgentRole, MessageType, PlanStep
from .state import PlanExecuteState


class PlanReview(BaseModel):
    action: Literal["continue", "replan", "report"]
    revised_steps: list[str] = Field(default_factory=list)
    reason: str = ""


review_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是 Planner Agent，负责根据诊断证据动态复核计划。
只做规划决策，不调用运维工具，也不撰写最终报告。
信息充分或计划执行完毕时选择 report；计划仍合理时选择 continue；
只有证据表明计划方向错误时选择 replan，并给出精简后的剩余步骤。"""),
    ("user", "原始任务：{task}\n剩余计划：{plan}\n已有证据：{evidence}"),
])


class PlannerAgent:
    role = AgentRole.PLANNER

    async def plan(self, state: PlanExecuteState) -> dict[str, Any]:
        # 延迟加载知识库和工具依赖，避免导入 Agent 契约时连接外部服务。
        from .planner import planner as create_legacy_plan

        legacy_output = await create_legacy_plan(state)
        steps = [
            PlanStep(step_id=f"step-{index}", objective=objective).model_dump()
            for index, objective in enumerate(legacy_output.get("plan", []), 1)
        ]
        if not steps:
            steps = [PlanStep(step_id="step-1", objective="收集并分析当前系统状态").model_dump()]

        correlation_id = state.get("correlation_id", "default")
        message = AgentMessage.create(
            correlation_id=correlation_id,
            sender=self.role,
            recipient=AgentRole.DIAGNOSIS,
            message_type=MessageType.PLAN_CREATED,
            payload={"steps": steps},
        )
        return {"plan": steps, "agent_messages": [message.model_dump(mode="json")], "next_agent": "diagnosis", "approval_granted": False}

    async def review(self, state: PlanExecuteState) -> dict[str, Any]:
        plan = state.get("plan", [])
        evidence = state.get("evidence", [])
        if not plan or len(evidence) >= 8:
            decision = PlanReview(action="report", reason="计划完成或达到执行上限")
        else:
            try:
                llm = ChatQwen(model=config.rag_model, api_key=config.dashscope_api_key, temperature=0)
                chain = review_prompt | llm.with_structured_output(PlanReview)
                decision = await chain.ainvoke({
                    "task": state.get("input", ""),
                    "plan": plan,
                    "evidence": evidence,
                })
                if not isinstance(decision, PlanReview):
                    decision = PlanReview.model_validate(decision)
            except Exception as exc:
                logger.warning(f"Planner Agent 复核失败，沿用剩余计划: {exc}")
                decision = PlanReview(action="continue", reason="复核降级")

        correlation_id = state.get("correlation_id", "default")
        if decision.action == "report":
            message = AgentMessage.create(
                correlation_id=correlation_id,
                sender=self.role,
                recipient=AgentRole.REPORT,
                message_type=MessageType.REPORT_REQUEST,
                payload={"reason": decision.reason, "evidence_count": len(evidence)},
            )
            return {"next_agent": "report", "agent_messages": [message.model_dump(mode="json")]}

        updates: dict[str, Any] = {"next_agent": "diagnosis"}
        message_type = MessageType.EXECUTION_REQUEST
        if decision.action == "replan" and decision.revised_steps:
            revised = [
                PlanStep(step_id=f"replan-{index}", objective=objective).model_dump()
                for index, objective in enumerate(decision.revised_steps[: len(plan)], 1)
            ]
            updates["plan"] = revised
            message_type = MessageType.PLAN_UPDATED
        message = AgentMessage.create(
            correlation_id=correlation_id,
            sender=self.role,
            recipient=AgentRole.DIAGNOSIS,
            message_type=message_type,
            payload={"plan": updates.get("plan", plan), "reason": decision.reason},
        )
        updates["agent_messages"] = [message.model_dump(mode="json")]
        return updates
