from pathlib import Path
import re


DOC_DIR = Path(__file__).parents[1] / "aiops-docs"

EXPECTED_FILES = {
    "cpu_high_usage.md",
    "memory_high_usage.md",
    "disk_high_usage.md",
    "service_unavailable.md",
    "slow_response.md",
    "high_error_rate.md",
    "database_slow_query.md",
    "database_connection_pool_exhausted.md",
    "redis_connection_failure.md",
    "container_restart_loop.md",
    "network_dns_failure.md",
    "jvm_frequent_full_gc.md",
    "thread_pool_exhausted.md",
}

REQUIRED_HEADINGS = {
    "## 适用场景与检索关键词",
    "## 告警定义与影响",
    "## 排查前必须确认的信息",
    "## 证据驱动的排查流程",
    "## 现象、证据与结论判断表",
    "## 常见原因与处理方案",
    "## 分级处置与风险控制",
    "## 修复验证",
    "## 常见误判",
    "## 预防措施",
    "## 关联告警",
}

ALLOWED_TOOLS = {
    "get_current_time",
    "get_current_timestamp",
    "query_prometheus_alerts",
    "query_cpu_metrics",
    "query_memory_metrics",
    "search_topic_by_service_name",
    "get_topic_info_by_name",
    "search_log",
    "restart_service",
}

DEMO_QUERIES = {
    "cpu_high_usage.md": ("CPU", "load average"),
    "memory_high_usage.md": ("OOM", "内存泄漏"),
    "high_error_rate.md": ("HTTP 5xx", "错误率"),
    "database_slow_query.md": ("slow query", "慢查询"),
    "database_connection_pool_exhausted.md": (
        "connection pool exhausted",
        "连接池耗尽",
    ),
    "redis_connection_failure.md": ("Redis", "connection refused"),
    "container_restart_loop.md": ("OOMKilled", "exit code 137"),
    "network_dns_failure.md": ("NXDOMAIN", "DNS"),
    "jvm_frequent_full_gc.md": ("Full GC", "stop-the-world"),
    "thread_pool_exhausted.md": ("RejectedExecutionException", "线程池"),
}


def _runbooks():
    return sorted(DOC_DIR.glob("*.md"))


def test_expected_runbook_files_exist():
    assert {path.name for path in _runbooks()} == EXPECTED_FILES


def test_runbooks_have_required_sections_and_no_banned_content():
    for path in _runbooks():
        content = path.read_text(encoding="utf-8")
        headings = set(re.findall(r"^## .+$", content, re.MULTILINE))

        assert REQUIRED_HEADINGS <= headings, path.name
        assert "query_logs" not in content, path.name
        assert "@company.com" not in content, path.name
        assert "internal-docs/" not in content, path.name
        assert "不能仅凭" in content, path.name
        assert "升级人工" in content, path.name


def test_only_real_tools_are_referenced():
    for path in _runbooks():
        content = path.read_text(encoding="utf-8")
        referenced = set(re.findall(r"`([a-z][a-z0-9_]+)`", content))
        tool_like = {
            name
            for name in referenced
            if name.startswith(("get_", "query_", "search_", "restart_"))
        }

        assert tool_like <= ALLOWED_TOOLS, (path.name, tool_like - ALLOWED_TOOLS)


def test_restart_service_requires_approval():
    for path in _runbooks():
        content = path.read_text(encoding="utf-8")
        if "`restart_service`" in content:
            assert "人工审批" in content, path.name


def test_demo_keywords_are_present_in_target_runbooks():
    for filename, keywords in DEMO_QUERIES.items():
        content = (DOC_DIR / filename).read_text(encoding="utf-8").lower()
        assert all(keyword.lower() in content for keyword in keywords), filename


def test_every_runbook_produces_nonempty_chunks():
    from app.services.document_splitter_service import document_splitter_service

    for path in _runbooks():
        chunks = document_splitter_service.split_document(
            path.read_text(encoding="utf-8"), str(path)
        )

        assert chunks, path.name
        assert all(chunk.page_content.strip() for chunk in chunks), path.name
        assert all(chunk.metadata.get("_file_name") == path.name for chunk in chunks)
