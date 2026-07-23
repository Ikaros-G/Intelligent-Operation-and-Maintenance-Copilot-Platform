# Container Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Monitor six Docker containers in Prometheus and Grafana and let the Chat Agent query those metrics through deterministic natural-language aliases.

**Architecture:** A pinned cAdvisor container exports Docker cgroup metrics to the existing Prometheus service. The Monitor MCP owns canonical container names, alias resolution, and PromQL construction; Grafana and the Chat Agent consume the same Prometheus series.

**Tech Stack:** Docker Compose, cAdvisor v0.57.0, Prometheus 3.5, Grafana 12.1, FastMCP, Python unittest.

## Global Constraints

- Monitor exactly `aiops-api`, `aiops-celery-worker`, `aiops-mcp-monitor`, `aiops-mcp-cls`, `milvus-standalone`, and `aiops-redis`.
- Never generate metric values or silently choose an ambiguous container alias.
- Keep cAdvisor port 8080 internal to the Compose network.
- Preserve existing process-level `query_cpu_metrics` and `query_memory_metrics` behavior.
- Ignore Git operations because this workspace is not a valid Git repository.

---

### Task 1: cAdvisor And Prometheus Collection

**Files:**
- Modify: `docker-compose.yml`
- Modify: `observability/prometheus.yml`
- Create: `tests/test_container_observability_config.py`

**Interfaces:**
- Produces Prometheus target `job="cadvisor"` at `cadvisor:8080`.
- Produces cAdvisor series containing Docker container identity labels.

- [ ] Write a unittest that parses the Compose and Prometheus text and asserts the pinned image, read-only host mounts, no published 8080 port, and the `cadvisor:8080` scrape target.
- [ ] Run `python tests/test_container_observability_config.py -v`; expect failures because cAdvisor is absent.
- [ ] Add `cadvisor` to Compose with `ghcr.io/google/cadvisor:v0.57.0`, required read-only mounts, privileged access, and `expose: [8080]`; add the Prometheus scrape job.
- [ ] Re-run the configuration test; expect all assertions to pass.
- [ ] Start cAdvisor and restart Prometheus, then verify `/api/v1/targets` reports `cadvisor` as `UP` and inspect actual identity labels before writing application PromQL.

### Task 2: Deterministic Container Metric Tools

**Files:**
- Modify: `mcp_servers/monitor_server.py`
- Create: `tests/test_container_monitor_tools.py`

**Interfaces:**
- Produces `resolve_container_alias(query: str) -> dict[str, Any]`.
- Produces MCP tools `list_monitored_containers()` and `query_container_metrics(target, metric, start_time=None, end_time=None, interval="1m")`.

- [ ] Write tests for canonical names, Chinese/English aliases, `Celery任务 -> aiops-celery-worker`, ambiguous `Agent -> candidates`, unsupported targets, mocked CPU/memory Prometheus results, and unavailable series.
- [ ] Run the new unittest in `aiops-mcp-monitor`; expect missing-function failures.
- [ ] Implement the canonical registry and normalization without model-based matching.
- [ ] Implement Prometheus instant/range helpers and list discovery using the identity label confirmed in Task 1.
- [ ] Implement CPU, memory working set, network RX/TX, and filesystem read/write queries with structured source, unit, time window, points, and statistics.
- [ ] Re-run new tests plus `tests/test_monitoring_truthfulness.py`; expect all tests to pass.

### Task 3: Chat Agent Tool Selection Rules

**Files:**
- Modify: `app/services/rag_agent_service.py`
- Modify: `tests/test_container_monitor_tools.py`

**Interfaces:**
- Consumes Monitor MCP tools from Task 2.
- Produces truthful natural-language routing for container resource questions.

- [ ] Add prompt assertions requiring alias discovery, container-versus-host distinction, candidate confirmation on ambiguity, and no fabricated values.
- [ ] Run the prompt test and confirm it fails on the current system prompt.
- [ ] Update the system prompt so named aliases call `query_container_metrics`, absent targets call `list_monitored_containers`, and ambiguous results are presented for confirmation.
- [ ] Restart Monitor MCP and API so MCP tool schemas are reloaded.
- [ ] Verify `Celery任务的CPU占用` resolves to `aiops-celery-worker`; verify `Agent CPU` returns candidates rather than a guessed metric.

### Task 4: Provisioned Grafana Dashboard

**Files:**
- Create: `observability/grafana/dashboards/container-resource-overview.json`
- Extend: `tests/test_container_observability_config.py`

**Interfaces:**
- Consumes cAdvisor Prometheus series from Task 1.
- Produces Grafana dashboard UID `container-resource-overview` in folder `AIOps Copilot`.

- [ ] Add JSON validation tests for dashboard UID, six-container variable restriction, refresh interval, and required CPU/memory/network/filesystem/availability panels.
- [ ] Run the test and confirm failure because the dashboard is absent.
- [ ] Create the provisioned dashboard with overview rankings and a container selector, using the actual cAdvisor identity label.
- [ ] Restart Grafana and query its health/dashboard APIs to verify provisioning.
- [ ] Check each panel PromQL through the Prometheus API and verify at least one result for every supported running container.

### Task 5: End-To-End Verification

**Files:**
- Update tests only if a verified runtime label differs from the documented cAdvisor label.

**Interfaces:**
- Verifies the complete cAdvisor -> Prometheus -> Grafana/Agent path.

- [ ] Run Python syntax checks and all focused unittests.
- [ ] Verify Prometheus targets `aiops-api` and `cadvisor` are `UP`.
- [ ] Query current CPU and memory for all six canonical containers.
- [ ] Call the default streaming chat endpoint with `Celery任务的CPU占用` and assert the answer names `aiops-celery-worker`, cites cAdvisor/Prometheus, and contains no error event.
- [ ] Call it with `Agent CPU` and assert it asks for clarification with multiple candidates.
- [ ] Verify Grafana dashboard API returns UID `container-resource-overview` and no container panel query is empty for a running target.

