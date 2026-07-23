"""Verify Tencent CLS SearchLog without printing log content."""

import json
import time

from mcp_servers.cls_server import list_cls_topics, search_log


topics_result = list_cls_topics(limit=20)
topics = topics_result.get("topics", [])
if not topics:
    print(json.dumps({"success": False, "message": "No accessible CLS topics"}))
    raise SystemExit(1)

topic = topics[0]
end_time = int(time.time() * 1000)
result = search_log(
    topic_id=topic["topic_id"],
    region_code=topic["region_code"],
    start_time=end_time - 60 * 60 * 1000,
    end_time=end_time,
    query="",
    limit=10,
)
sample = None
if result.get("logs"):
    first = result["logs"][0]
    content = first.get("content")
    sample = {
        "timestamp": first.get("timestamp"),
        "source_present": bool(first.get("source")),
        "file_name_present": bool(first.get("file_name")),
        "content_type": type(content).__name__,
        "content_fields": sorted(content) if isinstance(content, dict) else [],
    }
print(
    json.dumps(
        {
            "success": result.get("success"),
            "data_source": result.get("data_source"),
            "topic_id": result.get("topic_id"),
            "topic_name": topic.get("topic_name"),
            "region_code": result.get("region_code"),
            "total": result.get("total"),
            "request_id": result.get("request_id"),
            "list_over": result.get("list_over"),
            "sample_metadata": sample,
            "error_code": result.get("error_code"),
            "error": result.get("error"),
        },
        ensure_ascii=False,
        indent=2,
    )
)
