"""
通用 Plan-Execute-Replan 服务
基于 LangGraph 官方教程实现
"""

import time
from typing import AsyncGenerator, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from loguru import logger

from app.agent.aiops import DiagnosisAgent, PlanExecuteState, PlannerAgent, ReportAgent
from app.core.persistence import close_checkpointer, create_async_checkpointer
from app.agent.aiops.security import ToolPolicy
from app.core.observability import WORKFLOW_DURATION


# 节点名称常量
NODE_PLANNER_AGENT = "planner_agent"
NODE_DIAGNOSIS_AGENT = "diagnosis_agent"
NODE_PLANNER_REVIEW = "planner_review"
NODE_REPORT_AGENT = "report_agent"
NODE_HUMAN_APPROVAL = "human_approval"


class AIOpsService:
    """通用 Plan-Execute-Replan 服务"""

    def __init__(self):
        """初始化服务"""
        self.planner_agent = PlannerAgent()
        self.diagnosis_agent = DiagnosisAgent()
        self.report_agent = ReportAgent()
        self.checkpointer = MemorySaver()
        self.graph = self._build_graph()
        logger.info("Multi-Agent AIOps Service 初始化完成")

    def _build_graph(self):
        """构建 Plan-Execute-Replan 工作流"""
        logger.info("构建工作流图...")

        # 创建状态图
        workflow = StateGraph(PlanExecuteState)

        # 三个独立 Agent；Planner 的 plan/review 是同一 Agent 的两个协作阶段
        workflow.add_node(NODE_PLANNER_AGENT, self.planner_agent.plan)
        workflow.add_node(NODE_DIAGNOSIS_AGENT, self.diagnosis_agent.execute)
        workflow.add_node(NODE_PLANNER_REVIEW, self.planner_agent.review)
        workflow.add_node(NODE_REPORT_AGENT, self.report_agent.generate)
        workflow.add_node(NODE_HUMAN_APPROVAL, self._human_approval)

        # 设置入口点
        workflow.set_entry_point(NODE_PLANNER_AGENT)

        # 定义边
        workflow.add_edge(NODE_DIAGNOSIS_AGENT, NODE_PLANNER_REVIEW)
        workflow.add_edge(NODE_REPORT_AGENT, END)

        workflow.add_conditional_edges(
            NODE_PLANNER_AGENT,
            self.route_before_diagnosis,
            {NODE_DIAGNOSIS_AGENT: NODE_DIAGNOSIS_AGENT, NODE_HUMAN_APPROVAL: NODE_HUMAN_APPROVAL},
        )
        workflow.add_conditional_edges(
            NODE_HUMAN_APPROVAL,
            lambda state: NODE_DIAGNOSIS_AGENT if state.get("approval_granted") else NODE_REPORT_AGENT,
            {NODE_DIAGNOSIS_AGENT: NODE_DIAGNOSIS_AGENT, NODE_REPORT_AGENT: NODE_REPORT_AGENT},
        )

        # replanner 的条件边
        workflow.add_conditional_edges(
            NODE_PLANNER_REVIEW,
            self.route_after_review,
            {
                NODE_DIAGNOSIS_AGENT: NODE_DIAGNOSIS_AGENT,
                NODE_REPORT_AGENT: NODE_REPORT_AGENT,
                NODE_HUMAN_APPROVAL: NODE_HUMAN_APPROVAL,
            }
        )

        # 编译工作流
        compiled_graph = workflow.compile(checkpointer=self.checkpointer)

        logger.info("工作流图构建完成")
        return compiled_graph

    async def enable_persistent_checkpoints(self) -> None:
        """Recompile the graph with Redis persistence after application startup."""
        self.checkpointer = await create_async_checkpointer()
        self.graph = self._build_graph()

    async def close(self) -> None:
        await close_checkpointer(self.checkpointer)

    @staticmethod
    def route_after_review(state: PlanExecuteState) -> str:
        """Route the Planner Agent's handoff without inspecting LLM internals."""
        if state.get("next_agent") == "report" or not state.get("plan"):
            return NODE_REPORT_AGENT
        if AIOpsService.route_before_diagnosis(state) == NODE_HUMAN_APPROVAL:
            return NODE_HUMAN_APPROVAL
        return NODE_DIAGNOSIS_AGENT

    @staticmethod
    def route_before_diagnosis(state: PlanExecuteState) -> str:
        plan = state.get("plan", [])
        if plan and ToolPolicy.requires_approval(str(plan[0].get("objective", ""))) and not state.get("approval_granted"):
            return NODE_HUMAN_APPROVAL
        return NODE_DIAGNOSIS_AGENT

    @staticmethod
    def _human_approval(state: PlanExecuteState) -> Dict[str, Any]:
        step = state.get("plan", [{}])[0]
        answer = interrupt({
            "type": "high_risk_action",
            "step_id": step.get("step_id"),
            "objective": step.get("objective"),
            "message": "该操作需要管理员人工审核",
        })
        approved = isinstance(answer, dict) and answer.get("approved") is True
        if approved:
            return {
                "approval_granted": True,
                "approval_reason": str(answer.get("reason", "")),
                "approved_tools": ToolPolicy.high_risk_tools_for(str(step.get("objective", ""))),
            }
        return {
            "approval_granted": False,
            "approval_reason": str(answer.get("reason", "审批拒绝")) if isinstance(answer, dict) else "审批拒绝",
            "plan": [],
            "next_agent": "report",
            "evidence": [{"step_id": step.get("step_id", ""), "objective": step.get("objective", ""), "summary": "高风险操作未获批准，未执行", "success": False}],
        }

    async def execute(
        self,
        user_input: str,
        session_id: str = "default",
        operator_role: str = "viewer",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        执行 Plan-Execute-Replan 流程

        Args:
            user_input: 用户的任务描述
            session_id: 会话ID

        Yields:
            Dict[str, Any]: 流式事件
        """
        logger.info(f"[会话 {session_id}] 开始执行任务: {user_input}")
        started = time.perf_counter()

        try:
            # 初始化状态
            initial_state: PlanExecuteState = {
                "input": user_input,
                "plan": [],
                "past_steps": [],
                "total_steps": 0,
                "completed_step_count": 0,
                "remaining_step_count": 0,
                "evidence": [],
                "agent_messages": [],
                "next_agent": "planner",
                "correlation_id": session_id,
                "operator_role": operator_role,
                "approval_granted": False,
                "approval_reason": "",
                "approved_tools": [],
                "response": "",
            }

            # 流式执行工作流
            config_dict = {
                "configurable": {
                    "thread_id": session_id
                }
            }

            async for stream_mode, event in self.graph.astream(
                input=initial_state,
                config=config_dict,
                stream_mode=["updates", "custom"]
            ):
                if stream_mode == "custom":
                    if isinstance(event, dict):
                        yield event
                    continue

                # 解析事件
                for node_name, node_output in event.items():
                    logger.info(f"节点 '{node_name}' 输出事件")

                    # 根据节点类型生成不同的事件
                    if node_name == NODE_PLANNER_AGENT:
                        yield self._format_planner_event(node_output)

                    elif node_name == NODE_DIAGNOSIS_AGENT:
                        yield self._format_executor_event(node_output)

                    elif node_name == NODE_PLANNER_REVIEW:
                        yield self._format_replanner_event(node_output)

                    elif node_name == NODE_REPORT_AGENT:
                        yield self._format_report_event(node_output)

                    elif node_name == "__interrupt__":
                        yield self._format_approval_event(node_output)

            # 获取最终状态
            final_state = await self.graph.aget_state(config_dict)
            final_response = ""

            # 安全地获取响应（处理 values 可能为 None 的情况）
            if final_state and final_state.values:
                final_response = final_state.values.get("response", "")

            if final_state and final_state.next:
                WORKFLOW_DURATION.labels(status="interrupted").observe(time.perf_counter() - started)
                return

            duration_seconds = time.perf_counter() - started
            WORKFLOW_DURATION.labels(status="success").observe(duration_seconds)
            logger.info(
                f"[会话 {session_id}] 任务执行完成, duration_seconds={duration_seconds:.3f}"
            )

            # 指标必须在完成事件之前记录；SSE 消费者收到 complete 后会停止迭代。
            yield {
                "type": "complete",
                "stage": "complete",
                "message": "任务执行完成",
                "response": final_response
            }

        except Exception as e:
            logger.error(f"[会话 {session_id}] 任务执行失败: {e}", exc_info=True)
            WORKFLOW_DURATION.labels(status="error").observe(time.perf_counter() - started)
            yield {
                "type": "error",
                "stage": "error",
                "message": "任务执行失败，请使用请求 ID 查询服务日志"
            }

    async def diagnose(
        self,
        session_id: str = "default",
        operator_role: str = "viewer",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        AIOps 诊断接口（兼容旧接口）

        Args:
            session_id: 会话ID

        Yields:
            Dict[str, Any]: 诊断过程的流式事件
        """
        # 使用固定的 AIOps 任务描述
        from textwrap import dedent
        aiops_task = dedent("""诊断当前系统是否存在告警，如果存在告警请详细分析告警原因并生成诊断报告，诊断报告输出格式要求：
                ```
                # 告警分析报告

                ---

                ## 📋 活跃告警清单

                | 告警名称 | 级别 | 目标服务 | 首次触发时间 | 最新触发时间 | 状态 |
                |---------|------|----------|-------------|-------------|------|
                | [告警1名称] | [级别] | [服务名] | [时间] | [时间] | 活跃 |
                | [告警2名称] | [级别] | [服务名] | [时间] | [时间] | 活跃 |

                ---

                ## 🔍 告警根因分析1 - [告警名称]

                ### 告警详情
                - **告警级别**: [级别]
                - **受影响服务**: [服务名]
                - **持续时间**: [X分钟]

                ### 症状描述
                [根据监控指标描述症状]

                ### 日志证据
                [引用查询到的关键日志]

                ### 根因结论
                [基于证据得出的根本原因]

                ---

                ## 🛠️ 处理方案执行1 - [告警名称]

                ### 已执行的排查步骤
                1. [步骤1]
                2. [步骤2]

                ### 处理建议
                [给出具体的处理建议]

                ### 预期效果
                [说明预期的效果]

                ---

                ## 🔍 告警根因分析2 - [告警名称]
                [如果有第2个告警，重复上述格式]

                ---

                ## 📊 结论

                ### 整体评估
                [总结所有告警的整体情况]

                ### 关键发现
                - [发现1]
                - [发现2]

                ### 后续建议
                1. [建议1]
                2. [建议2]

                ### 风险评估
                [评估当前风险等级和影响范围]
                ```

                **重要提醒**：
                - 最终输出必须是纯 Markdown 文本，不要包含 JSON 结构
                - 所有内容必须基于工具查询的真实数据，严禁编造
                - 如果某个步骤失败，在结论中如实说明，不要跳过""")

        async for event in self.execute(aiops_task, session_id, operator_role):
            # 转换事件格式以兼容旧的 API
            if event.get("type") == "complete":
                # 将 response 包装为 diagnosis 格式
                yield {
                    "type": "complete",
                    "stage": "diagnosis_complete",
                    "message": "诊断流程完成",
                    "diagnosis": {
                        "status": "completed",
                        "report": event.get("response", "")
                    }
                }
            else:
                yield event

    async def resume(self, session_id: str, approval: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        config_dict = {"configurable": {"thread_id": session_id}}
        async for stream_mode, event in self.graph.astream(
            Command(resume=approval),
            config=config_dict,
            stream_mode=["updates", "custom"],
        ):
            if stream_mode == "custom":
                if isinstance(event, dict):
                    yield event
                continue
            for node_name, node_output in event.items():
                if node_name == NODE_HUMAN_APPROVAL:
                    yield {"type": "approval", "stage": "approval_resolved", "message": "审批结果已提交"}
                elif node_name == NODE_DIAGNOSIS_AGENT:
                    yield self._format_executor_event(node_output)
                elif node_name == NODE_PLANNER_REVIEW:
                    yield self._format_replanner_event(node_output)
                elif node_name == NODE_REPORT_AGENT:
                    yield self._format_report_event(node_output)
                elif node_name == "__interrupt__":
                    yield self._format_approval_event(node_output)
        final_state = await self.graph.aget_state(config_dict)
        if final_state.next:
            return
        response = final_state.values.get("response", "") if final_state.values else ""
        yield {"type": "complete", "stage": "complete", "message": "任务执行完成", "response": response}

    def _format_planner_event(self, state: Dict | None) -> Dict:
        """格式化 Planner 节点事件"""
        if not state:
            return {
                "type": "status",
                "stage": "planner",
                "message": "规划节点执行中"
            }

        plan = state.get("plan", [])
        public_plan = [item.get("objective", str(item)) if isinstance(item, dict) else str(item) for item in plan]
        total_steps = int(state.get("total_steps", len(public_plan)))

        return {
            "type": "plan",
            "stage": "plan_created",
            "message": f"执行计划已制定，共 {total_steps} 个步骤",
            "plan": public_plan,
            "total_steps": total_steps,
        }

    def _format_executor_event(self, state: Dict | None) -> Dict:
        """格式化 Executor 节点事件"""
        if not state:
            return {
                "type": "status",
                "stage": "executor",
                "message": "执行节点运行中"
            }

        plan = state.get("plan", [])
        past_steps = state.get("past_steps", [])

        if past_steps:
            last_step, _ = past_steps[-1]
            completed_step_count = int(state.get("completed_step_count", len(past_steps)))
            total_steps = int(state.get("total_steps", completed_step_count + len(plan)))
            remaining_step_count = int(
                state.get("remaining_step_count", max(total_steps - completed_step_count, 0))
            )
            return {
                "type": "step_complete",
                "stage": "step_executed",
                "message": f"步骤执行完成 ({completed_step_count}/{total_steps})：{last_step}",
                "current_step": last_step,
                "current_step_index": completed_step_count,
                "total_steps": total_steps,
                "remaining_steps": remaining_step_count,
            }
        else:
            return {
                "type": "status",
                "stage": "executor",
                "message": "开始执行步骤"
            }

    def _format_replanner_event(self, state: Dict | None) -> Dict:
        """格式化 Replanner 节点事件"""
        if not state:
            return {
                "type": "status",
                "stage": "replanner",
                "message": "评估节点运行中"
            }

        plan = state.get("plan", [])
        completed_step_count = int(state.get("completed_step_count", 0))
        total_steps = int(state.get("total_steps", completed_step_count + len(plan)))
        remaining_step_count = int(state.get("remaining_step_count", len(plan)))
        handing_off = state.get("next_agent") != "diagnosis"

        if handing_off and remaining_step_count:
            message = (
                f"Planner Agent 复核完成，已完成 {completed_step_count}/{total_steps}；"
                f"现有证据已足够，剩余 {remaining_step_count} 个步骤不再执行，转交报告 Agent"
            )
        elif handing_off:
            message = (
                f"Planner Agent 复核完成，全部 {total_steps} 个计划步骤已完成，转交报告 Agent"
            )
        else:
            message = (
                f"Planner Agent 复核完成，继续诊断（已完成 {completed_step_count}/{total_steps}）"
            )

        return {
            "type": "status",
            "stage": "planner_review",
            "message": message,
            "completed_step_count": completed_step_count,
            "total_steps": total_steps,
            "remaining_steps": remaining_step_count,
        }

    def _format_report_event(self, state: Dict | None) -> Dict:
        """保持原有 report SSE 事件契约。"""
        report = state.get("response", "") if state else ""
        return {
            "type": "report",
            "stage": "final_report",
            "message": "Report Agent 已生成最终报告",
            "report": report,
        }

    def _format_approval_event(self, state: Any) -> Dict:
        interrupts = list(state or [])
        payload = getattr(interrupts[0], "value", {}) if interrupts else {}
        return {"type": "approval_required", "stage": "human_review", "message": "等待管理员审批", "approval": payload}


# 全局单例
aiops_service = AIOpsService()
