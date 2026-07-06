import pytest

from app.agent.aiops.security import OperatorRole, ToolPolicy, ToolRisk


def test_high_risk_tool_requires_admin_and_explicit_approval():
    policy = ToolPolicy()

    assert policy.risk_for("restart_service") is ToolRisk.HIGH
    assert not policy.is_allowed("restart_service", OperatorRole.VIEWER, approved=False)
    assert not policy.is_allowed("restart_service", OperatorRole.ADMIN, approved=False)
    assert policy.is_allowed("restart_service", OperatorRole.ADMIN, approved=True)


def test_read_only_tools_are_available_to_viewers():
    policy = ToolPolicy()

    assert policy.is_allowed("query_prometheus_alerts", OperatorRole.VIEWER, approved=False)
    assert policy.is_allowed("search_log", OperatorRole.VIEWER, approved=False)


def test_filter_tools_removes_unauthorized_tools():
    class FakeTool:
        def __init__(self, name):
            self.name = name

    policy = ToolPolicy()
    tools = [FakeTool("search_log"), FakeTool("restart_service")]

    filtered = policy.filter_tools(tools, OperatorRole.VIEWER, approved=False)

    assert [tool.name for tool in filtered] == ["search_log"]


def test_approval_is_scoped_to_named_high_risk_tool():
    class FakeTool:
        def __init__(self, name):
            self.name = name

    tools = [FakeTool("restart_service"), FakeTool("delete_resource")]
    filtered = ToolPolicy().filter_tools(
        tools,
        OperatorRole.ADMIN,
        approved=True,
        approved_tools=["restart_service"],
    )

    assert [tool.name for tool in filtered] == ["restart_service"]


@pytest.mark.parametrize("text", ["重启 payment-service", "restart api", "执行命令清理缓存", "扩容服务"])
def test_high_risk_plan_step_is_detected(text):
    assert ToolPolicy.requires_approval(text)
