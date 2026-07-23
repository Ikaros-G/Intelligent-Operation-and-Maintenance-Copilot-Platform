from prometheus_client import generate_latest

from app.core.observability import record_tool_call


def test_tool_metrics_use_bounded_status_labels():
    record_tool_call("search_log", "success", 0.25)

    metrics = generate_latest().decode("utf-8")
    assert 'aiops_tool_calls_total{status="success",tool="search_log"}' in metrics
    assert "aiops_tool_duration_seconds" in metrics
