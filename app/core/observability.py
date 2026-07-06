"""Prometheus metrics and OpenTelemetry bootstrap."""

import time
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.config import config

HTTP_REQUESTS = Counter("aiops_http_requests_total", "HTTP requests", ["method", "route", "status_class"])
HTTP_DURATION = Histogram("aiops_http_request_duration_seconds", "HTTP request duration", ["method", "route"])
TOOL_CALLS = Counter("aiops_tool_calls_total", "Agent tool calls", ["tool", "status"])
TOOL_DURATION = Histogram("aiops_tool_duration_seconds", "Agent tool duration", ["tool"])
WORKFLOW_DURATION = Histogram("aiops_workflow_duration_seconds", "AIOps workflow duration", ["status"])
RAG_CACHE = Counter("aiops_rag_cache_total", "RAG cache accesses", ["result"])


def record_tool_call(tool: str, status: str, duration_seconds: float) -> None:
    bounded_status = status if status in {"success", "error", "timeout", "rejected", "degraded"} else "error"
    TOOL_CALLS.labels(tool=tool, status=bounded_status).inc()
    TOOL_DURATION.labels(tool=tool).observe(duration_seconds)


def setup_observability(app: FastAPI) -> None:
    @app.middleware("http")
    async def metrics_and_request_id(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid4())
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            HTTP_REQUESTS.labels(method=request.method, route=route, status_class="5xx").inc()
            HTTP_DURATION.labels(method=request.method, route=route).observe(time.perf_counter() - started)
            raise
        route = getattr(request.scope.get("route"), "path", "unmatched")
        status_class = f"{response.status_code // 100}xx"
        HTTP_REQUESTS.labels(method=request.method, route=route, status_class=status_class).inc()
        HTTP_DURATION.labels(method=request.method, route=route).observe(time.perf_counter() - started)
        response.headers["x-request-id"] = request_id
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    if not config.otel_enabled:
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": config.otel_service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=config.otel_exporter_otlp_endpoint, insecure=config.otel_exporter_otlp_endpoint.startswith("http://"))))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics")
    HTTPXClientInstrumentor().instrument()
