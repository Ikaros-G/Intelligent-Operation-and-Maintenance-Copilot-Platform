"""
通用 Plan-Execute-Replan 状态定义
基于 LangGraph 官方教程实现
"""

from typing import Any, List, TypedDict, Annotated
import operator


class PlanExecuteState(TypedDict):
    """Plan-Execute-Replan 状态"""
    
    # 用户输入（任务描述）
    input: str
    
    # 执行计划（步骤列表）
    plan: List[dict[str, Any]]
    
    # 已执行的步骤历史
    # 使用 operator.add 实现追加式更新（而非覆盖）
    past_steps: Annotated[List[tuple], operator.add]

    # Diagnosis Agent 生产的结构化证据
    evidence: Annotated[List[dict[str, Any]], operator.add]

    # Agent 间的可追踪消息信封
    agent_messages: Annotated[List[dict[str, Any]], operator.add]

    # Planner 复核后指定的下一位 Agent
    next_agent: str

    # 当前会话，用作跨 Agent 消息 correlation_id
    correlation_id: str

    # 代码层权限与 Human-in-the-Loop 状态
    operator_role: str
    approval_granted: bool
    approval_reason: str
    approved_tools: List[str]
    
    # 最终响应/报告
    response: str
