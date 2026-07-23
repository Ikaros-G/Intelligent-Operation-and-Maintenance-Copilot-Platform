import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_servers import cls_server, monitor_server


ROOT = Path(__file__).resolve().parents[1]


class ClsToolTruthfulnessTest(unittest.TestCase):
    def test_cls_source_contains_no_generated_demo_data(self):
        source = (ROOT / "mcp_servers" / "cls_server.py").read_text(encoding="utf-8")

        for forbidden in ("mock_topics", "正在同步元数据", "模拟地区映射表"):
            self.assertNotIn(forbidden, source)

    @patch.object(cls_server, "_call_cls_api")
    def test_topic_listing_uses_real_describe_topics(self, call_cls):
        call_cls.return_value = {
            "Topics": [],
            "TotalCount": 0,
            "RequestId": "request-real-list",
        }

        result = cls_server.list_cls_topics(region_code="ap-beijing", limit=50)

        self.assertTrue(result["success"])
        self.assertEqual(result["topics"], [])
        self.assertEqual(result["data_source"], "tencentcloud_cls")
        call_cls.assert_called_once_with(
            "DescribeTopics",
            "ap-beijing",
            {"Filters": [], "Offset": 0, "Limit": 50, "BizType": 0},
        )

    @patch.object(cls_server, "_call_cls_api")
    def test_topic_search_uses_tencent_cls_describe_topics(self, call_cls):
        call_cls.return_value = {
            "Topics": [
                {
                    "TopicId": "topic-real-1",
                    "TopicName": "api-gateway-service",
                    "LogsetId": "logset-real-1",
                    "CreateTime": "2026-07-01 12:00:00",
                    "Index": True,
                    "Status": True,
                    "Describes": "production logs",
                    "Tags": [],
                }
            ],
            "TotalCount": 1,
            "RequestId": "request-real-1",
        }

        result = cls_server.search_topic_by_service_name(
            "api-gateway", region_code="ap-shanghai"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["data_source"], "tencentcloud_cls")
        self.assertEqual(result["topics"][0]["topic_id"], "topic-real-1")
        call_cls.assert_called_once_with(
            "DescribeTopics",
            "ap-shanghai",
            {
                "Filters": [{"Key": "topicName", "Values": ["api-gateway"]}],
                "Offset": 0,
                "Limit": 100,
                "BizType": 0,
            },
        )

    @patch.object(cls_server, "_call_cls_api")
    def test_log_search_returns_only_tencent_cls_results(self, call_cls):
        call_cls.return_value = {
            "Context": "next-page-token",
            "ListOver": True,
            "Analysis": False,
            "Results": [
                {
                    "Time": 1784426400000,
                    "TopicId": "topic-real-1",
                    "TopicName": "api-gateway-service",
                    "Source": "10.0.0.8",
                    "FileName": "/var/log/app.log",
                    "HostName": "node-1",
                    "LogJson": '{"level":"ERROR","message":"database timeout"}',
                    "RawLog": "",
                }
            ],
            "AnalysisRecords": None,
            "RequestId": "request-real-2",
        }

        result = cls_server.search_log(
            topic_id="topic-real-1",
            start_time=1784422800000,
            end_time=1784426400000,
            query="level:ERROR",
            limit=20,
            region_code="ap-shanghai",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["data_source"], "tencentcloud_cls")
        self.assertEqual(result["logs"][0]["content"]["message"], "database timeout")
        self.assertIn("+08:00", result["query_window"]["start"])
        self.assertIn("+08:00", result["query_window"]["end"])
        self.assertEqual(result["query_window"]["timezone"], "Asia/Shanghai")
        call_cls.assert_called_once_with(
            "SearchLog",
            "ap-shanghai",
            {
                "TopicId": "topic-real-1",
                "From": 1784422800000,
                "To": 1784426400000,
                "QueryString": "level:ERROR",
                "QuerySyntax": 1,
                "Limit": 20,
                "Sort": "desc",
                "UseNewAnalysis": True,
            },
        )


class RestartToolTruthfulnessTest(unittest.TestCase):
    def test_monitor_source_does_not_claim_unexecuted_restart_was_accepted(self):
        source = (ROOT / "mcp_servers" / "monitor_server.py").read_text(encoding="utf-8")
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        restart_compose = (ROOT / "docker-compose.restart-tools.yml").read_text(encoding="utf-8")

        self.assertNotIn("示例环境已记录重启请求，未执行系统命令", source)
        self.assertIn("ENABLE_DOCKER_RESTART", source)
        self.assertNotIn("/var/run/docker.sock:/var/run/docker.sock", compose)
        self.assertIn("/var/run/docker.sock:/var/run/docker.sock", restart_compose)
        self.assertIn('ENABLE_DOCKER_RESTART: "true"', restart_compose)

    @patch.object(monitor_server, "_restart_docker_container")
    def test_restart_service_reports_completed_only_after_docker_call(self, restart):
        restart.return_value = None

        result = monitor_server.restart_service(
            "Celery任务", "管理员批准后恢复卡住的索引任务"
        )

        restart.assert_called_once_with("aiops-celery-worker")
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["executed"])
        self.assertEqual(result["data_source"], "docker_engine")


if __name__ == "__main__":
    unittest.main()
