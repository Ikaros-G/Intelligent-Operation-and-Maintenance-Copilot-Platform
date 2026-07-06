# 补充技术使用说明

## 异步知识库

上传 `POST /api/upload` 返回 HTTP 202：

```json
{"task_id":"...","state":"PENDING","status_url":"/api/tasks/...","filename":"runbook.md"}
```

Celery Worker 从 Redis Broker 消费任务，完成文档读取、切分、向量化与 Milvus 索引。客户端通过 `GET /api/tasks/{task_id}` 查询 `PENDING / STARTED / RETRY / SUCCESS / FAILURE`。

启动 Worker：

```bash
celery -A app.tasks.celery_app:celery_app worker --loglevel=INFO
```

## Redis 状态与缓存

- DB 0：RAG 热点检索缓存和 LangGraph Checkpoint；
- DB 1：Celery Broker；
- DB 2：Celery Result Backend；
- Redis Checkpoint 启动失败时降级到 `MemorySaver`，日志会记录 `langgraph_checkpointer_fallback`。

## 高风险审批

普通只读诊断无需高权限。以管理员身份启动可能包含高风险步骤的诊断：

```bash
curl -N -X POST http://localhost:9900/api/aiops \
  -H "Content-Type: application/json" \
  -H "X-Operator-Role: admin" \
  -H "X-Operator-Key: $OPS_API_KEY" \
  -d '{"session_id":"incident-42"}'
```

工作流遇到重启、扩缩容、执行命令等步骤会返回 `approval_required` 并暂停。使用相同会话恢复：

```bash
curl -N -X POST http://localhost:9900/api/aiops/incident-42/approval \
  -H "Content-Type: application/json" \
  -H "X-Operator-Key: $OPS_API_KEY" \
  -d '{"approved":true,"reviewer":"oncall-admin","reason":"已确认变更窗口"}'
```

权限校验、工具白名单和风险等级均在代码层执行，Prompt 不是安全边界。

## 可靠性

每次工具调用都有：

- `asyncio.timeout` 超时；
- Tenacity 瞬态错误重试；
- 按工具隔离的熔断状态；
- 不向模型暴露内部异常和凭据的结构化降级结果。

## 可观测性

- Prometheus：`http://localhost:9900/metrics`；
- Grafana：`http://localhost:3000`；
- Tempo Trace 通过 OpenTelemetry Collector 接收；
- HTTP 响应携带 `x-request-id`；
- Dashboard 包含 HTTP 请求率/p95、工具成功率与工作流 p95。

## RAGAS

安装评测依赖并运行：

```bash
pip install -e ".[evaluation]"
python -m evaluation.run_ragas
```

评测结果写入 `evaluation/report.json`，包含 Context Recall、Answer Relevancy、Faithfulness。

## 容器启动

复制环境模板、填写密钥后启动完整平台：

```bash
cp .env.example .env
docker compose up --build -d
```

Compose 包含 FastAPI、Celery、Redis 8、Milvus、两个 MCP Server、Prometheus、OpenTelemetry Collector、Tempo 和 Grafana。
