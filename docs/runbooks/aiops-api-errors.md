# AIOps API 高错误率

1. 在 Grafana 查看 HTTP 5xx 对应的 route 与 Trace。
2. 使用 `x-request-id` 在应用日志中定位具体请求。
3. 检查 Redis、Milvus、MCP 和模型服务健康状态；无法恢复时停止高风险操作入口。
