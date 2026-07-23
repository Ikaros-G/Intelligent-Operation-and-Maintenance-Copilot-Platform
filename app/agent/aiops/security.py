"""Code-enforced tool authorization and high-risk action classification."""

from collections.abc import Iterable
from enum import StrEnum
from typing import Any


class OperatorRole(StrEnum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


class ToolRisk(StrEnum):
    READ = "read"
    WRITE = "write"
    HIGH = "high"


class ToolPolicy:
    HIGH_RISK_TOOLS = {"restart_service", "scale_service", "execute_command", "delete_resource"}
    WRITE_TOOLS = {"acknowledge_alert", "create_ticket"}
    HIGH_RISK_TERMS = ("重启", "restart", "扩容", "缩容", "scale", "执行命令", "清理缓存", "删除")

    def risk_for(self, tool_name: str) -> ToolRisk:
        if tool_name in self.HIGH_RISK_TOOLS:
            return ToolRisk.HIGH
        if tool_name in self.WRITE_TOOLS:
            return ToolRisk.WRITE
        return ToolRisk.READ

    def is_allowed(self, tool_name: str, role: OperatorRole, approved: bool) -> bool:
        risk = self.risk_for(tool_name)
        if risk is ToolRisk.READ:
            return True
        if risk is ToolRisk.WRITE:
            return role in {OperatorRole.OPERATOR, OperatorRole.ADMIN}
        return role is OperatorRole.ADMIN and approved

    def filter_tools(
        self,
        tools: Iterable[Any],
        role: OperatorRole,
        approved: bool,
        approved_tools: Iterable[str] | None = None,
    ) -> list[Any]:
        scoped_approvals = set(approved_tools or [])
        return [
            tool
            for tool in tools
            if self.is_allowed(getattr(tool, "name", ""), role, approved)
            and (self.risk_for(getattr(tool, "name", "")) is not ToolRisk.HIGH or not scoped_approvals or getattr(tool, "name", "") in scoped_approvals)
        ]

    @classmethod
    def requires_approval(cls, objective: str) -> bool:
        lowered = objective.lower()
        return any(term in lowered for term in cls.HIGH_RISK_TERMS)

    @classmethod
    def high_risk_tools_for(cls, objective: str) -> list[str]:
        lowered = objective.lower()
        tools = []
        if "重启" in lowered or "restart" in lowered:
            tools.append("restart_service")
        if any(term in lowered for term in ("扩容", "缩容", "scale")):
            tools.append("scale_service")
        if any(term in lowered for term in ("执行命令", "清理缓存")):
            tools.append("execute_command")
        if "删除" in lowered:
            tools.append("delete_resource")
        return tools
