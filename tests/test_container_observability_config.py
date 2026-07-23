import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"
PROMETHEUS = ROOT / "observability" / "prometheus.yml"
DASHBOARD = ROOT / "observability" / "grafana" / "dashboards" / "container-resource-overview.json"
DATASOURCES = ROOT / "observability" / "grafana" / "provisioning" / "datasources" / "datasources.yml"


class ContainerObservabilityConfigTest(unittest.TestCase):
    def test_compose_defines_internal_pinned_cadvisor(self):
        compose = COMPOSE.read_text(encoding="utf-8")

        self.assertIn("cadvisor:", compose)
        self.assertIn("ghcr.io/google/cadvisor:v0.57.0", compose)
        self.assertIn("container_name: aiops-cadvisor", compose)
        self.assertIn("expose: [\"8080\"]", compose)
        self.assertNotIn('ports: ["8080:8080"]', compose)
        for mount in (
            "/:/rootfs:ro",
            "/var/run:/var/run:ro",
            "/sys:/sys:ro",
            "/var/lib/docker:/var/lib/docker:ro",
            "/dev/disk:/dev/disk:ro",
        ):
            self.assertIn(mount, compose)

    def test_prometheus_scrapes_cadvisor(self):
        prometheus = PROMETHEUS.read_text(encoding="utf-8")

        self.assertIn("job_name: cadvisor", prometheus)
        self.assertIn("targets: [cadvisor:8080]", prometheus)

    def test_dashboard_has_required_container_panels(self):
        dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
        datasources = DATASOURCES.read_text(encoding="utf-8")

        self.assertEqual(dashboard["uid"], "container-resource-overview")
        self.assertEqual(dashboard["refresh"], "15s")
        self.assertIn("uid: prometheus", datasources)
        titles = {panel["title"] for panel in dashboard["panels"]}
        self.assertTrue({
            "Container availability",
            "Current CPU usage",
            "Current memory working set",
            "CPU usage trend",
            "Memory working set trend",
            "Network receive / transmit",
            "Filesystem read / write",
            "Container start time",
        }.issubset(titles))

        variables = dashboard["templating"]["list"]
        container_variable = next(item for item in variables if item["name"] == "container")
        self.assertEqual(container_variable["datasource"]["uid"], "prometheus")
        query = container_variable["query"]["query"]
        for container in (
            "aiops-api",
            "aiops-celery-worker",
            "aiops-mcp-monitor",
            "aiops-mcp-cls",
            "milvus-standalone",
            "aiops-redis",
        ):
            self.assertIn(container, query)

    def test_datasource_uid_migration_is_deterministic(self):
        datasources = DATASOURCES.read_text(encoding="utf-8")

        self.assertIn("deleteDatasources:", datasources)
        self.assertGreaterEqual(datasources.count("name: Prometheus"), 2)
        self.assertGreaterEqual(datasources.count("name: Tempo"), 2)
        self.assertIn("uid: prometheus", datasources)
        self.assertIn("uid: tempo", datasources)


if __name__ == "__main__":
    unittest.main()
