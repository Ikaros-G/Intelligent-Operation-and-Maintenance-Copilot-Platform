"""Verify real CLS topic-name filtering without printing credentials."""

import json

from mcp_servers.cls_server import search_topic_by_service_name


result = search_topic_by_service_name("Nginx Demo", region_code="ap-chongqing")
print(
    json.dumps(
        {
            "success": result.get("success"),
            "total": result.get("total"),
            "failed_regions": result.get("failed_regions"),
            "request_ids": result.get("request_ids"),
            "topic_names": [topic.get("topic_name") for topic in result.get("topics", [])],
        },
        ensure_ascii=False,
        indent=2,
    )
)
