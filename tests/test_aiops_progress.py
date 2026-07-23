import unittest
from unittest.mock import patch

from app.agent.aiops.diagnosis_agent import DiagnosisAgent
from app.agent.aiops.planner_agent import PlannerAgent
from app.services.aiops_service import AIOpsService


class AIOpsProgressTest(unittest.IsolatedAsyncioTestCase):
    async def test_planner_records_the_original_plan_size(self):
        async def fake_plan(_state):
            return {"plan": ["查询告警", "查询 CPU", "查询日志"]}

        with patch("app.agent.aiops.planner.planner", new=fake_plan):
            result = await PlannerAgent().plan({"correlation_id": "progress-test"})

        self.assertEqual(result["total_steps"], 3)
        self.assertEqual(result["completed_step_count"], 0)
        self.assertEqual(result["remaining_step_count"], 3)

    async def test_diagnosis_returns_cumulative_progress(self):
        async def fake_execute(_state):
            return {"past_steps": [("查询日志", "没有错误日志")]}

        state = {
            "correlation_id": "progress-test",
            "plan": [
                {"step_id": "step-3", "objective": "查询日志"},
                {"step_id": "step-4", "objective": "生成结论"},
            ],
            "past_steps": [("查询告警", "无告警"), ("查询 CPU", "正常")],
            "total_steps": 4,
            "completed_step_count": 2,
        }

        with patch("app.agent.aiops.executor.executor", new=fake_execute):
            result = await DiagnosisAgent().execute(state)

        self.assertEqual(result["total_steps"], 4)
        self.assertEqual(result["completed_step_count"], 3)
        self.assertEqual(result["remaining_step_count"], 1)

    def test_step_event_uses_cumulative_progress_not_update_list_length(self):
        event = AIOpsService()._format_executor_event({
            "plan": [{"step_id": "step-4", "objective": "生成结论"}],
            "past_steps": [("查询日志", "没有错误日志")],
            "total_steps": 8,
            "completed_step_count": 3,
            "remaining_step_count": 5,
        })

        self.assertEqual(event["message"], "步骤执行完成 (3/8)：查询日志")
        self.assertEqual(event["current_step_index"], 3)
        self.assertEqual(event["total_steps"], 8)
        self.assertEqual(event["remaining_steps"], 5)

    def test_review_event_explains_why_remaining_steps_were_not_executed(self):
        event = AIOpsService()._format_replanner_event({
            "next_agent": "report",
            "total_steps": 8,
            "completed_step_count": 3,
            "remaining_step_count": 5,
        })

        self.assertEqual(
            event["message"],
            "Planner Agent 复核完成，已完成 3/8；现有证据已足够，剩余 5 个步骤不再执行，转交报告 Agent",
        )


if __name__ == "__main__":
    unittest.main()
