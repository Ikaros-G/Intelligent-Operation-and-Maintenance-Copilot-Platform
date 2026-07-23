# Container Observability Design

## Goal

Add factual container-level monitoring for the local AIOps demo. Grafana and the
conversation Agent must use the same Prometheus data to report CPU, memory,
network, filesystem, and availability for these containers:

- `aiops-api`
- `aiops-celery-worker`
- `aiops-mcp-monitor`
- `aiops-mcp-cls`
- `milvus-standalone`
- `aiops-redis`

## Architecture

The data path is:

```text
Docker containers -> cAdvisor -> Prometheus -> Grafana
                                           -> Monitor MCP -> Chat Agent
```

The Compose stack will run the pinned `ghcr.io/google/cadvisor:v0.57.0` image.
cAdvisor will be available only on the Compose network because the demo does not
need to expose its host-inspection endpoint to the LAN. Prometheus will scrape
`cadvisor:8080` every 15 seconds using the `cadvisor` job.

The existing process metrics for `aiops-api` remain unchanged. Container metrics
are an additional source and are selected by the Docker container name label.

## Metric Semantics

CPU percentage is calculated from:

```promql
rate(container_cpu_usage_seconds_total[5m]) * 100
```

One fully used CPU core is 100%, so a multi-core container may exceed 100%.

Current memory uses `container_memory_working_set_bytes`. Memory percentage is
reported only when cAdvisor exposes a finite positive container specification
limit. Network receive/transmit and filesystem read/write are rates over the
requested time window. Missing series, scrape failures, and invalid limits must
be reported as unavailable rather than replaced with generated values.

## Grafana Dashboard

Provision a new dashboard named `Container Resource Overview` in the existing
`AIOps Copilot` folder. It contains:

- target-container availability table;
- current CPU and memory ranking;
- per-container CPU time series;
- memory working-set bytes and optional limit percentage;
- network receive/transmit rates;
- filesystem read/write rates;
- container start time;
- a container variable restricted to the six supported names.

Panels use restrained operational styling and the existing Prometheus data
source. Empty panels display a clear no-data state.

## Assistant Tools

The Monitor MCP adds:

- `list_monitored_containers`: discovers the supported containers that currently
  have cAdvisor series and returns canonical name, aliases, and availability.
- `query_container_metrics`: resolves a user-facing target and queries CPU,
  memory, network, or filesystem data for a time range.

Both tools return `data_source=prometheus/cadvisor`, the canonical container
name, query window, unit, data availability, points, and summary statistics.

## Alias Resolution

Aliases are resolved deterministically in Monitor MCP, not guessed by the model.
Normalization is case-insensitive and ignores spaces, underscores, and hyphens.

| User terminology | Canonical container |
| --- | --- |
| assistant, API, chat Agent, diagnosis Agent | `aiops-api` |
| Celery, async task, indexing task, knowledge upload task | `aiops-celery-worker` |
| monitor MCP, monitoring tool | `aiops-mcp-monitor` |
| CLS, classifier, intent recognition | `aiops-mcp-cls` |
| Milvus, vector database, knowledge database | `milvus-standalone` |
| Redis, cache, session cache, task queue | `aiops-redis` |

Chinese equivalents are included in the implementation registry. Exact canonical
names take priority. A phrase mapping to multiple candidates returns an ambiguous
result and asks the user to choose. It must never silently select a candidate.

The Agent prompt will call `list_monitored_containers` when a target is absent,
use `query_container_metrics` for resolved targets, distinguish container metrics
from host metrics, and state that DashScope cloud inference CPU is not included.

## Error Handling And Security

- cAdvisor mounts required Docker host paths read-only and runs privileged only
  where required by Docker Desktop compatibility.
- Port 8080 is not published to the Windows host.
- Prometheus and Grafana remain the only user-facing monitoring interfaces.
- Prometheus request failures return structured unavailable responses.
- Unsupported and ambiguous aliases return candidates instead of fabricated data.
- Existing service-level CPU and memory tools remain backward compatible.

## Verification

Automated checks cover alias resolution, ambiguity, PromQL construction,
unavailable results, Compose configuration, Prometheus scrape configuration, and
Grafana dashboard structure. Live verification requires:

1. cAdvisor is healthy and Prometheus reports the `cadvisor` target as `UP`.
2. All six canonical container names have CPU and memory series.
3. Grafana provisions the dashboard and its panels return data.
4. The Agent answers natural-language requests such as `Celery任务的CPU占用` with
   `aiops-celery-worker` data and identifies the source as cAdvisor.
5. Ambiguous requests such as `Agent CPU` return candidates without querying a
   guessed container.

