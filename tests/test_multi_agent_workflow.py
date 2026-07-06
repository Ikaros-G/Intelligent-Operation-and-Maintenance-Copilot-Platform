from app.agent.aiops.diagnosis_agent import DiagnosisAgent
from app.agent.aiops.planner_agent import PlannerAgent
from app.agent.aiops.report_agent import ReportAgent
from app.services.aiops_service import (
    NODE_DIAGNOSIS_AGENT,
    NODE_PLANNER_AGENT,
    NODE_PLANNER_REVIEW,
    NODE_REPORT_AGENT,
    AIOpsService,
)


async def _collect_events(generator):
    return [event async for event in generator]


def test_workflow_is_composed_of_three_independent_agents():
    service = AIOpsService()

    assert isinstance(service.planner_agent, PlannerAgent)
    assert isinstance(service.diagnosis_agent, DiagnosisAgent)
    assert isinstance(service.report_agent, ReportAgent)
    assert {
        NODE_PLANNER_AGENT,
        NODE_DIAGNOSIS_AGENT,
        NODE_PLANNER_REVIEW,
        NODE_REPORT_AGENT,
    }.issubset(service.graph.nodes)


def test_planner_review_routes_to_report_when_requested():
    state = {"next_agent": "report", "plan": []}

    assert AIOpsService.route_after_review(state) == NODE_REPORT_AGENT


def test_planner_review_routes_back_to_diagnosis_for_remaining_work():
    state = {"next_agent": "diagnosis", "plan": [{"step_id": "step-2"}]}

    assert AIOpsService.route_after_review(state) == NODE_DIAGNOSIS_AGENT


async def test_agents_handoff_through_graph_without_external_services(monkeypatch):
    async def fake_plan(self, state):
        return {"plan": [{"step_id": "step-1", "objective": "查询告警", "suggested_tools": []}], "next_agent": "diagnosis"}

    async def fake_execute(self, state):
        return {
            "plan": [],
            "past_steps": [("查询告警", "没有活跃告警")],
            "evidence": [{"step_id": "step-1", "objective": "查询告警", "summary": "没有活跃告警", "success": True}],
            "next_agent": "planner",
        }

    async def fake_review(self, state):
        return {"next_agent": "report"}

    async def fake_report(self, state):
        return {"response": "# 诊断报告\n\n系统正常", "next_agent": "complete"}

    monkeypatch.setattr(PlannerAgent, "plan", fake_plan)
    monkeypatch.setattr(PlannerAgent, "review", fake_review)
    monkeypatch.setattr(DiagnosisAgent, "execute", fake_execute)
    monkeypatch.setattr(ReportAgent, "generate", fake_report)

    service = AIOpsService()
    events = await _collect_events(service.execute("诊断系统", "test-session"))

    assert [event["type"] for event in events] == ["plan", "step_complete", "status", "report", "complete"]
    assert events[-1]["response"] == "# 诊断报告\n\n系统正常"


async def test_high_risk_workflow_pauses_and_resumes_after_approval(monkeypatch):
    async def fake_plan(self, state):
        return {
            "plan": [{"step_id": "step-1", "objective": "重启 payment-service", "suggested_tools": ["restart_service"]}],
            "next_agent": "diagnosis",
            "approval_granted": False,
        }

    async def fake_execute(self, state):
        assert state["approval_granted"] is True
        assert state["approved_tools"] == ["restart_service"]
        return {
            "plan": [],
            "past_steps": [("重启 payment-service", "已受理")],
            "evidence": [{"step_id": "step-1", "objective": "重启 payment-service", "summary": "已受理", "success": True}],
            "next_agent": "planner",
            "approval_granted": False,
            "approved_tools": [],
        }

    async def fake_review(self, state):
        return {"next_agent": "report"}

    async def fake_report(self, state):
        return {"response": "# 已审批并执行", "next_agent": "complete"}

    monkeypatch.setattr(PlannerAgent, "plan", fake_plan)
    monkeypatch.setattr(PlannerAgent, "review", fake_review)
    monkeypatch.setattr(DiagnosisAgent, "execute", fake_execute)
    monkeypatch.setattr(ReportAgent, "generate", fake_report)

    service = AIOpsService()
    initial_events = await _collect_events(service.execute("处理故障", "approval-session", "admin"))
    assert initial_events[-1]["type"] == "approval_required"
    assert all(event["type"] != "complete" for event in initial_events)

    resumed_events = await _collect_events(
        service.resume("approval-session", {"approved": True, "reviewer": "admin", "reason": "变更窗口"})
    )
    assert resumed_events[-1]["type"] == "complete"
    assert resumed_events[-1]["response"] == "# 已审批并执行"
