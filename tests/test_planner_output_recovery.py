import unittest
from unittest.mock import patch

from langchain_core.runnables import RunnableLambda

from app.agent.aiops import planner as planner_module


class PlannerOutputRecoveryTest(unittest.IsolatedAsyncioTestCase):
    async def test_planner_uses_fallback_when_qwen_output_cannot_be_parsed(self):
        class FakeMCPClient:
            async def get_tools(self):
                return []

        class FakeKnowledgeTool:
            async def ainvoke(self, _):
                return ""

        class FakeQwen:
            def __init__(self, **kwargs):
                pass

            def with_structured_output(self, schema, *, include_raw=False):
                self_test.assertTrue(include_raw)
                return RunnableLambda(
                    lambda _: {
                        "raw": None,
                        "parsed": None,
                        "parsing_error": KeyError("step"),
                    }
                )

        async def fake_mcp_client():
            return FakeMCPClient()

        self_test = self
        with (
            patch.object(planner_module, "retrieve_knowledge", FakeKnowledgeTool()),
            patch.object(planner_module, "get_mcp_client_with_retry", fake_mcp_client),
            patch.object(planner_module, "ChatQwen", FakeQwen),
        ):
            result = await planner_module.planner({"input": "诊断当前系统告警"})

        self.assertEqual(result["plan"], planner_module.FALLBACK_PLAN_STEPS)
        self.assertTrue(result["plan"][0].startswith("使用 query_prometheus_alerts"))


if __name__ == "__main__":
    unittest.main()
