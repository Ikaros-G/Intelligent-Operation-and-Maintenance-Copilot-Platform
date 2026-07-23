import unittest
from unittest.mock import patch

from mcp_servers import monitor_server


class ContainerMonitorToolsTest(unittest.TestCase):
    def test_resolves_natural_language_aliases(self):
        cases = {
            "Celery任务的CPU占用": "aiops-celery-worker",
            "知识库索引任务内存": "aiops-celery-worker",
            "向量数据库最近一小时CPU": "milvus-standalone",
            "任务队列的内存": "aiops-redis",
            "监控MCP网络流量": "aiops-mcp-monitor",
            "腾讯云日志查询CPU": "aiops-mcp-cls",
            "aiops-api": "aiops-api",
        }

        for query, expected in cases.items():
            with self.subTest(query=query):
                result = monitor_server.resolve_container_alias(query)
                self.assertEqual(result["status"], "resolved")
                self.assertEqual(result["canonical_name"], expected)

    def test_generic_agent_alias_is_ambiguous(self):
        result = monitor_server.resolve_container_alias("Agent CPU")

        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(
            set(result["candidates"]),
            {"aiops-api", "aiops-mcp-monitor", "aiops-mcp-cls"},
        )

    def test_unknown_target_is_not_guessed(self):
        result = monitor_server.resolve_container_alias("订单服务CPU")

        self.assertEqual(result["status"], "unsupported")
        self.assertIsNone(result["canonical_name"])

    @patch("mcp_servers.monitor_server._prometheus_instant_query")
    def test_lists_only_supported_containers_with_live_availability(self, query):
        query.return_value = [
            {"metric": {"name": "aiops-api"}, "value": [1, "1"]},
            {"metric": {"name": "aiops-redis"}, "value": [1, "1"]},
        ]

        result = monitor_server.list_monitored_containers()

        self.assertTrue(result["success"])
        self.assertEqual(len(result["containers"]), 6)
        availability = {item["name"]: item["available"] for item in result["containers"]}
        self.assertTrue(availability["aiops-api"])
        self.assertTrue(availability["aiops-redis"])
        self.assertFalse(availability["milvus-standalone"])
        self.assertIn("container_last_seen", query.call_args.args[0])
        self.assertNotIn("\\-", query.call_args.args[0])

    @patch("mcp_servers.monitor_server._prometheus_query_range")
    def test_cpu_query_uses_resolved_cadvisor_container(self, query_range):
        query_range.return_value = [{
            "metric": {},
            "values": [[1000, "2.5"], [1060, "4.5"]],
        }]

        result = monitor_server.query_container_metrics(
            "Celery任务",
            metric="cpu",
            start_time="2026-07-19 09:00:00",
            end_time="2026-07-19 09:01:00",
        )

        self.assertTrue(result["data_available"])
        self.assertEqual(result["container_name"], "aiops-celery-worker")
        self.assertEqual(result["data_source"], "prometheus/cadvisor")
        self.assertEqual(result["unit"], "percent_of_one_cpu_core")
        self.assertEqual(result["statistics"]["latest"], 4.5)
        promql = query_range.call_args.args[0]
        self.assertIn("container_cpu_usage_seconds_total", promql)
        self.assertIn('name="aiops-celery-worker"', promql)

    @patch("mcp_servers.monitor_server._prometheus_query_range")
    def test_memory_query_reports_megabytes(self, query_range):
        query_range.return_value = [{
            "metric": {},
            "values": [[1000, "128.25"], [1060, "256.5"]],
        }]

        result = monitor_server.query_container_metrics(
            "Milvus",
            metric="memory",
            start_time="2026-07-19 09:00:00",
            end_time="2026-07-19 09:01:00",
        )

        self.assertEqual(result["container_name"], "milvus-standalone")
        self.assertEqual(result["unit"], "MiB")
        self.assertEqual(result["statistics"]["max"], 256.5)
        self.assertIn("container_memory_working_set_bytes", query_range.call_args.args[0])

    def test_ambiguous_target_returns_candidates_without_querying_prometheus(self):
        with patch("mcp_servers.monitor_server._prometheus_query_range") as query_range:
            result = monitor_server.query_container_metrics("Agent", metric="cpu")

        self.assertFalse(result["data_available"])
        self.assertEqual(result["resolution_status"], "ambiguous")
        self.assertGreater(len(result["candidates"]), 1)
        query_range.assert_not_called()

    def test_agent_prompt_uses_container_discovery_and_natural_aliases(self):
        from app.services.rag_agent_service import RagAgentService

        prompt = RagAgentService._build_system_prompt(object())

        self.assertIn("list_monitored_containers", prompt)
        self.assertIn("query_container_metrics", prompt)
        self.assertIn("自然语言别名", prompt)
        self.assertIn("候选容器", prompt)
        self.assertIn("容器指标不等于 Windows 宿主机指标", prompt)


if __name__ == "__main__":
    unittest.main()
