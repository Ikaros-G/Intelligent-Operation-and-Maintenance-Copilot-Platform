import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langgraph.config import get_stream_writer

from app.agent.aiops.diagnosis_agent import DiagnosisAgent
from app.agent.aiops.planner_agent import PlannerAgent
from app.agent.aiops.report_agent import ReportAgent
from app.core.observability import WORKFLOW_DURATION
from app.services.aiops_service import AIOpsService


class AIOpsReportStreamTest(unittest.IsolatedAsyncioTestCase):
    def test_workflow_histogram_is_ready_for_first_long_running_diagnosis(self):
        samples = [
            sample
            for metric in WORKFLOW_DURATION.collect()
            for sample in metric.samples
        ]
        statuses = {
            sample.labels.get("status")
            for sample in samples
            if sample.name == "aiops_workflow_duration_seconds_count"
        }
        upper_bounds = {
            sample.labels.get("le")
            for sample in samples
            if sample.name == "aiops_workflow_duration_seconds_bucket"
        }

        self.assertEqual(statuses, {"success", "error", "interrupted"})
        self.assertIn("300.0", upper_bounds)

    async def test_success_metric_is_recorded_before_complete_event_is_consumed(self):
        class CompletedGraph:
            async def astream(self, *args, **kwargs):
                if False:
                    yield None

            async def aget_state(self, _config):
                return SimpleNamespace(values={"response": "诊断完成"}, next=())

        service = AIOpsService()
        service.graph = CompletedGraph()

        with patch("app.services.aiops_service.WORKFLOW_DURATION") as duration:
            events = service.execute("诊断系统", "metrics-test")
            complete_event = await anext(events)

            self.assertEqual(complete_event["type"], "complete")
            duration.labels.assert_called_once_with(status="success")
            duration.labels.return_value.observe.assert_called_once()
            await events.aclose()

    async def test_report_chunks_are_forwarded_before_completion(self):
        async def fake_plan(self, state):
            return {
                "plan": [{"step_id": "step-1", "objective": "查询告警", "suggested_tools": []}],
                "next_agent": "diagnosis",
            }

        async def fake_execute(self, state):
            return {
                "plan": [],
                "past_steps": [("查询告警", "没有活跃告警")],
                "evidence": [
                    {
                        "step_id": "step-1",
                        "objective": "查询告警",
                        "summary": "没有活跃告警",
                        "success": True,
                    }
                ],
                "next_agent": "planner",
            }

        async def fake_review(self, state):
            return {"next_agent": "report"}

        async def fake_report(self, state):
            writer = get_stream_writer()
            writer({"type": "report_chunk", "stage": "report_streaming", "data": "# 诊断"})
            writer({"type": "report_chunk", "stage": "report_streaming", "data": "报告"})
            return {"response": "# 诊断报告", "next_agent": "complete"}

        with (
            patch.object(PlannerAgent, "plan", fake_plan),
            patch.object(PlannerAgent, "review", fake_review),
            patch.object(DiagnosisAgent, "execute", fake_execute),
            patch.object(ReportAgent, "generate", fake_report),
        ):
            service = AIOpsService()
            events = [event async for event in service.execute("诊断系统", "stream-test")]

        event_types = [event["type"] for event in events]
        first_chunk = event_types.index("report_chunk")
        self.assertEqual(event_types[first_chunk:first_chunk + 2], ["report_chunk", "report_chunk"])
        self.assertLess(first_chunk, event_types.index("report"))
        self.assertLess(event_types.index("report"), event_types.index("complete"))


if __name__ == "__main__":
    unittest.main()
