import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GrafanaDashboardTest(unittest.TestCase):
    def test_container_start_time_formats_only_timestamp_column_as_date(self):
        dashboard_path = (
            ROOT
            / "observability"
            / "grafana"
            / "dashboards"
            / "container-resource-overview.json"
        )
        dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
        panel = next(
            panel
            for panel in dashboard["panels"]
            if panel["title"] == "Container start time"
        )

        self.assertNotIn("unit", panel["fieldConfig"]["defaults"])
        self.assertEqual(
            panel["transformations"][0]["options"]["renameByName"],
            {"name": "Container", "Value": "Started at"},
        )
        timestamp_override = panel["fieldConfig"]["overrides"][0]
        self.assertEqual(timestamp_override["matcher"]["options"], "Started at")
        self.assertIn(
            {"id": "unit", "value": "dateTimeAsIso"},
            timestamp_override["properties"],
        )


if __name__ == "__main__":
    unittest.main()
