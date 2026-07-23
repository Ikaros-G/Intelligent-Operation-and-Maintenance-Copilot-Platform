import unittest
from unittest.mock import patch

from mcp_servers import monitor_server


class FakeResponse:
    def __init__(self, result):
        self._result = result

    def raise_for_status(self):
        return None

    def json(self):
        return {"status": "success", "data": {"result": self._result}}


class FakeClient:
    def __init__(self, result, calls, *args, **kwargs):
        self.result = result
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def get(self, url, params):
        self.calls.append((url, params))
        return FakeResponse(self.result)


class MonitoringTruthfulnessTest(unittest.TestCase):
    def test_cpu_metrics_are_returned_from_prometheus(self):
        calls = []
        result = [{"metric": {}, "values": [[1000, "12.5"], [1300, "18.5"]]}]

        with patch(
            "mcp_servers.monitor_server.httpx.Client",
            side_effect=lambda *args, **kwargs: FakeClient(result, calls),
        ):
            response = monitor_server.query_cpu_metrics(
                service_name="aiops-api",
                start_time="2026-07-18 10:00:00",
                end_time="2026-07-18 10:05:00",
                interval="5m",
            )

        self.assertEqual(response["data_source"], "prometheus")
        self.assertTrue(response["data_available"])
        self.assertEqual(response["statistics"]["avg"], 15.5)
        self.assertEqual([point["value"] for point in response["data_points"]], [12.5, 18.5])
        self.assertIn("process_cpu_seconds_total", calls[0][1]["query"])
        self.assertIn('job="aiops-api"', calls[0][1]["query"])

    def test_missing_service_metrics_are_reported_as_unavailable(self):
        calls = []

        with patch(
            "mcp_servers.monitor_server.httpx.Client",
            side_effect=lambda *args, **kwargs: FakeClient([], calls),
        ):
            response = monitor_server.query_cpu_metrics("data-sync-service")

        self.assertEqual(response["data_source"], "prometheus")
        self.assertFalse(response["data_available"])
        self.assertEqual(response["data_points"], [])
        self.assertIsNone(response["alert_info"]["triggered"])
        self.assertIn("未找到", response["message"])

    def test_memory_reports_real_rss_without_inventing_percentage(self):
        calls = []
        result = [{"metric": {}, "values": [[1000, "268435456"], [1300, "536870912"]]}]

        with patch(
            "mcp_servers.monitor_server.httpx.Client",
            side_effect=lambda *args, **kwargs: FakeClient(result, calls),
        ):
            response = monitor_server.query_memory_metrics("aiops-api")

        self.assertEqual(response["metric_name"], "process_resident_memory_mb")
        self.assertEqual([point["value_mb"] for point in response["data_points"]], [256.0, 512.0])
        self.assertIsNone(response["alert_info"]["triggered"])
        self.assertIn("process_resident_memory_bytes", calls[0][1]["query"])

    def test_agent_prompt_forbids_guessing_service_and_fabricating_status(self):
        from app.services.rag_agent_service import RagAgentService

        prompt = RagAgentService._build_system_prompt(object())

        self.assertIn("不得猜测或默认使用任何服务名", prompt)
        self.assertIn("用户未明确提供服务名", prompt)
        self.assertIn("不能确认当前实际指标", prompt)
        self.assertIn("排查建议", prompt)


if __name__ == "__main__":
    unittest.main()
