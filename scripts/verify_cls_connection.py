"""Verify Tencent Cloud CLS access without printing credentials or log bodies."""

import json

from mcp_servers.cls_server import list_cls_topics


result = list_cls_topics(limit=20)
summary = {
    "success": result.get("success"),
    "total": result.get("total"),
    "regions_queried": result.get("regions_queried"),
    "failed_regions": result.get("failed_regions"),
    "request_ids": result.get("request_ids"),
    "topics": [
        {
            "topic_id": topic.get("topic_id"),
            "topic_name": topic.get("topic_name"),
            "region_code": topic.get("region_code"),
            "index_enabled": topic.get("index_enabled"),
        }
        for topic in result.get("topics", [])
    ],
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
