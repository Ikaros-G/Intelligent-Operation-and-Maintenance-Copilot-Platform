# AIOps Knowledge Runbooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `aiops-docs` 扩充为 13 篇证据驱动、工具名称准确、适合 RAG 检索和项目演示的运维 Runbook。

**Architecture:** 每个故障症状对应一个独立 Markdown 文件，所有文件采用统一的二级标题结构，并在开头放置告警名、中文症状和英文日志关键词。先用静态测试锁定文件集合、章节、工具白名单和安全提示，再分批改写文档，最后调用项目现有 Markdown 分片器验证索引输入。

**Tech Stack:** Markdown、Python 3.11、pytest、LangChain `MarkdownHeaderTextSplitter`

## Global Constraints

- 最终必须包含 5 篇完善文档和 8 篇新增文档，共 13 个 Markdown 文件。
- 只允许引用 `get_current_time`、`get_current_timestamp`、`query_prometheus_alerts`、`query_cpu_metrics`、`query_memory_metrics`、`search_topic_by_service_name`、`get_topic_info_by_name`、`search_log`、`restart_service`。
- `restart_service` 必须明确标注为需要人工审批的高风险操作。
- 不使用固定地域、固定日志主题、虚构联系人、虚构内部链接和不存在的 `query_logs`。
- 每篇文档必须包含证据判断、常见误判、修复验证和人工升级条件。
- 当前目录没有有效 Git 仓库，任务完成后不能创建提交；只保留文件级变更和测试结果。

---

### Task 1: Runbook 结构和工具约束测试

**Files:**
- Create: `tests/test_aiops_docs.py`
- Read: `docs/superpowers/specs/2026-07-18-aiops-knowledge-runbooks-design.md`

**Interfaces:**
- Consumes: `aiops-docs/*.md` UTF-8 文件。
- Produces: 对文件集合、必需章节、禁用内容、工具白名单和高风险操作说明的自动校验。

- [ ] **Step 1: 写入失败测试**

测试定义以下常量和断言：

```python
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
    "get_current_time", "get_current_timestamp", "query_prometheus_alerts",
    "query_cpu_metrics", "query_memory_metrics", "search_topic_by_service_name",
    "get_topic_info_by_name", "search_log", "restart_service",
}

def test_expected_runbook_files_exist():
    assert {path.name for path in DOC_DIR.glob("*.md")} == EXPECTED_FILES

def test_runbooks_have_required_sections_and_no_banned_content():
    for path in DOC_DIR.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        assert REQUIRED_HEADINGS <= set(re.findall(r"^## .+$", content, re.MULTILINE)), path.name
        assert "query_logs" not in content, path.name
        assert "@company.com" not in content, path.name
        assert "internal-docs/" not in content, path.name
        assert "不能仅凭" in content, path.name
        assert "升级人工" in content, path.name

def test_only_real_tools_are_referenced():
    for path in DOC_DIR.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        referenced = set(re.findall(r"`([a-z][a-z0-9_]+)`", content))
        tool_like = {name for name in referenced if name.startswith(("get_", "query_", "search_", "restart_"))}
        assert tool_like <= ALLOWED_TOOLS, (path.name, tool_like - ALLOWED_TOOLS)

def test_restart_service_requires_approval():
    for path in DOC_DIR.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        if "`restart_service`" in content:
            assert "人工审批" in content, path.name
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/test_aiops_docs.py -q`

Expected: FAIL，报告缺少 8 个文件，且现有 5 篇缺少统一章节并引用 `query_logs`。

- [ ] **Step 3: 保存失败结果作为后续批次基线**

Run: `pytest tests/test_aiops_docs.py -q 2>&1 | Select-Object -First 40`

Expected: 输出明确指向文件集合或章节约束，不出现测试代码自身异常。

---

### Task 2: 完善现有资源类 Runbook

**Files:**
- Modify: `aiops-docs/cpu_high_usage.md`
- Modify: `aiops-docs/memory_high_usage.md`
- Modify: `aiops-docs/disk_high_usage.md`

**Interfaces:**
- Consumes: Task 1 的统一章节和工具白名单。
- Produces: CPU、内存、磁盘三个可独立召回的资源故障 Runbook。

- [ ] **Step 1: 改写 CPU 文档**

加入 `HighCPUUsage`、负载高、单核打满、load average、throttling 等关键词；流程依次使用 `query_prometheus_alerts`、`query_cpu_metrics`、日志主题发现和 `search_log`。判断表必须区分流量增长、死循环、频繁 GC、慢依赖导致忙等待和容器 CPU 限流。

- [ ] **Step 2: 改写内存文档**

加入 `HighMemoryUsage`、OOM、RSS、working set、heap、memory leak 等关键词；流程使用 `query_memory_metrics` 和日志工具，区分缓存增长、堆泄漏、堆外内存、流量突增和容器 limit 过低。重启前应建议保留堆转储，但不得描述为 Agent 已执行。

- [ ] **Step 3: 改写磁盘文档**

加入 `HighDiskUsage`、inode、No space left on device、只读文件系统等关键词；明确项目没有磁盘专用指标工具，先查告警和日志，再给出 `df -h`、`df -i`、`du`、`find` 等人工只读命令。删除文件和 Docker prune 必须标注风险，不给出无确认直接执行的命令链。

- [ ] **Step 4: 运行局部约束测试**

Run: `pytest tests/test_aiops_docs.py::test_runbooks_have_required_sections_and_no_banned_content tests/test_aiops_docs.py::test_only_real_tools_are_referenced -q`

Expected: 新结构在三篇文档中通过；如果其他旧文档仍失败，失败文件只能是尚未改造的文档。

---

### Task 3: 完善现有可用性和性能 Runbook

**Files:**
- Modify: `aiops-docs/service_unavailable.md`
- Modify: `aiops-docs/slow_response.md`

**Interfaces:**
- Consumes: Task 1 的统一章节和工具白名单。
- Produces: 服务完全不可用与服务延迟升高两个边界清晰的 Runbook。

- [ ] **Step 1: 改写服务不可用文档**

加入健康检查失败、connection refused、HTTP 502/503、实例全下线等关键词；先查活动告警，再发现日志主题并查询启动失败、OOM、依赖连接失败和配置错误。`restart_service` 只能出现在证据确认后的高风险处置中，并明确人工审批、影响评估和回滚条件。

- [ ] **Step 2: 改写慢响应文档**

加入 P95/P99、timeout、upstream latency、请求堆积等关键词；判断流程同时查询 CPU、内存和日志，但不把任一单项升高直接当成根因。文档明确把 SQL 专项、连接池专项和线程池专项交给对应 Runbook。

- [ ] **Step 3: 运行现有文档测试**

Run: `pytest tests/test_aiops_docs.py::test_runbooks_have_required_sections_and_no_banned_content tests/test_aiops_docs.py::test_only_real_tools_are_referenced tests/test_aiops_docs.py::test_restart_service_requires_approval -q`

Expected: 现有 5 篇全部通过内容约束；文件集合测试仍因新增文档未完成而失败。

---

### Task 4: 新增 HTTP、数据库和 Redis Runbook

**Files:**
- Create: `aiops-docs/high_error_rate.md`
- Create: `aiops-docs/database_slow_query.md`
- Create: `aiops-docs/database_connection_pool_exhausted.md`
- Create: `aiops-docs/redis_connection_failure.md`

**Interfaces:**
- Consumes: 日志主题发现与 `search_log` 查询流程。
- Produces: 应用错误率、SQL 性能、数据库连接资源和缓存依赖四类 Runbook。

- [ ] **Step 1: 新增高错误率文档**

覆盖 `HighErrorRate`、HTTP 500/502/503/504、异常率和错误突增；通过告警、服务日志和资源指标区分应用异常、下游故障、网关问题、容量不足和发布回归。

- [ ] **Step 2: 新增数据库慢查询文档**

覆盖 slow query、query timeout、lock wait、full table scan；要求从日志提取 SQL 指纹、耗时、影响请求和时间相关性，再建议人工执行 EXPLAIN。不得仅凭响应慢判断数据库慢查询。

- [ ] **Step 3: 新增数据库连接池耗尽文档**

覆盖 too many connections、pool exhausted、timeout waiting for connection、connection leak；区分数据库最大连接数、应用连接泄漏、慢事务、实例扩容导致总连接数上升和网络断连。

- [ ] **Step 4: 新增 Redis 故障文档**

覆盖 Redis connection refused、timeout、READONLY、MOVED、缓存延迟和命中率下降；区分 Redis 不可达、连接池耗尽、热 key、大 key、主从切换和应用侧超时配置。

- [ ] **Step 5: 运行新增批次测试**

Run: `pytest tests/test_aiops_docs.py -q`

Expected: 章节和工具测试通过；文件集合测试仅报告尚缺 4 个运行时类文档。

---

### Task 5: 新增容器、网络、JVM 和线程池 Runbook

**Files:**
- Create: `aiops-docs/container_restart_loop.md`
- Create: `aiops-docs/network_dns_failure.md`
- Create: `aiops-docs/jvm_frequent_full_gc.md`
- Create: `aiops-docs/thread_pool_exhausted.md`

**Interfaces:**
- Consumes: 活动告警、CPU/内存指标、日志查询和人工只读命令。
- Produces: 应用运行时与基础网络四类 Runbook，完成 13 篇文件集合。

- [ ] **Step 1: 新增容器频繁重启文档**

覆盖 restart loop、CrashLoop、OOMKilled、exit code 137/143、health check failed；区分 OOM、启动配置、探针错误、依赖未就绪和人工发布。文档不得把一次正常重启判断为重启循环。

- [ ] **Step 2: 新增网络和 DNS 文档**

覆盖 DNS timeout、NXDOMAIN、connection reset、connection refused、packet loss；区分解析失败、端口未监听、防火墙、下游过载和连接复用问题，并给出 `nslookup`、`dig`、`curl -v`、`Test-NetConnection` 等人工只读检查。

- [ ] **Step 3: 新增 JVM Full GC 文档**

覆盖 Full GC、GC overhead limit exceeded、allocation failure、stop-the-world；结合 CPU、内存趋势和 GC 日志区分堆过小、泄漏、大对象、晋升失败和元空间问题。

- [ ] **Step 4: 新增线程池耗尽文档**

覆盖 active threads、queue full、RejectedExecutionException、request queue timeout；区分慢下游、锁竞争、任务执行过慢、线程泄漏和线程池配置不合理。

- [ ] **Step 5: 运行全部静态约束测试**

Run: `pytest tests/test_aiops_docs.py -q`

Expected: PASS，13 个文件全部满足结构、工具和安全约束。

---

### Task 6: 分片和检索关键词验证

**Files:**
- Modify: `tests/test_aiops_docs.py`
- Verify: `aiops-docs/*.md`

**Interfaces:**
- Consumes: 完成后的 13 篇 Markdown 文档和 `document_splitter_service.split_document(content, file_path)`。
- Produces: 每篇文档可被切分且关键故障问法能映射到唯一或明确的目标文档。

- [ ] **Step 1: 增加分片测试**

```python
from app.services.document_splitter_service import document_splitter_service

def test_every_runbook_produces_nonempty_chunks():
    for path in DOC_DIR.glob("*.md"):
        chunks = document_splitter_service.split_document(
            path.read_text(encoding="utf-8"), str(path)
        )
        assert chunks, path.name
        assert all(chunk.page_content.strip() for chunk in chunks), path.name
```

- [ ] **Step 2: 增加演示关键词覆盖测试**

```python
DEMO_QUERIES = {
    "cpu_high_usage.md": ("CPU", "load average"),
    "memory_high_usage.md": ("OOM", "内存泄漏"),
    "high_error_rate.md": ("HTTP 5xx", "错误率"),
    "database_slow_query.md": ("slow query", "慢查询"),
    "database_connection_pool_exhausted.md": ("connection pool exhausted", "连接池耗尽"),
    "redis_connection_failure.md": ("Redis", "connection refused"),
    "container_restart_loop.md": ("OOMKilled", "exit code 137"),
    "network_dns_failure.md": ("NXDOMAIN", "DNS"),
    "jvm_frequent_full_gc.md": ("Full GC", "stop-the-world"),
    "thread_pool_exhausted.md": ("RejectedExecutionException", "线程池"),
}

def test_demo_keywords_are_present_in_target_runbooks():
    for filename, keywords in DEMO_QUERIES.items():
        content = (DOC_DIR / filename).read_text(encoding="utf-8").lower()
        assert all(keyword.lower() in content for keyword in keywords), filename
```

- [ ] **Step 3: 运行知识库文档测试**

Run: `pytest tests/test_aiops_docs.py -q`

Expected: PASS。

- [ ] **Step 4: 运行项目回归测试**

Run: `pytest tests -q`

Expected: 现有项目测试和新增知识库测试全部通过；需要外部服务的集成测试若被环境跳过，应记录跳过原因。

- [ ] **Step 5: 输出文档统计**

Run: `Get-ChildItem aiops-docs -Filter *.md | Select-Object Name,Length`

Expected: 输出 13 个非空 Markdown 文件，新文档和改造文档均具有足够内容供分片器生成多个语义片段。

