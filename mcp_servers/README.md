# MCP Servers

项目包含两个 MCP Server。所有默认注册工具均返回真实数据或明确的失败/空结果，不生成演示指标、Topic 或日志。

## CLS Server

`cls_server.py` 运行在容器 `aiops-mcp-cls` 的 8003 端口，通过腾讯云 API 3.0 访问 Cloud Log Service。

工具：

- `get_current_timestamp`：读取本地系统时间，返回毫秒时间戳。
- `get_region_code_by_name`：腾讯云地域名称与地域代码映射，不声明资源一定存在。
- `list_cls_topics`：调用腾讯云 `DescribeTopics` 列出真实日志主题。
- `get_topic_info_by_name`：调用 `DescribeTopics` 精确查询主题名。
- `search_topic_by_service_name`：调用 `DescribeTopics` 按 Topic 名模糊或精确检索。
- `search_log`：调用腾讯云 `SearchLog` 查询真实日志。

需要配置：

```dotenv
TENCENTCLOUD_SECRET_ID=...
TENCENTCLOUD_SECRET_KEY=...
# 可选；逗号分隔。未配置时扫描代码内的常用地域清单。
TENCENTCLOUD_CLS_REGIONS=ap-chongqing
```

若容器通过项目的 8899 HTTPS relay 出网，`scripts/host_https_relay.py` 必须保留 `cls.tencentcloudapi.com:443` 白名单。

## Monitor Server

`monitor_server.py` 运行在容器 `aiops-mcp-monitor` 的 8004 端口。

默认工具：

- `list_monitored_containers`：通过 Prometheus/cAdvisor 核实可监控容器。
- `query_container_metrics`：查询容器 CPU、内存、网络和文件系统指标。
- `query_cpu_metrics`：查询指定 Prometheus job 的进程 CPU 指标。
- `query_memory_metrics`：查询指定 Prometheus job 的进程 RSS 内存。

所有指标工具均返回 `data_source`。Prometheus 无数据或请求失败时返回 `data_available=false`，不会生成数值。

## 可选重启工具

`restart_service` 是真实 Docker Engine 重启操作，默认不注册。启用它会让监控 MCP 获得 Docker socket 访问权，只应在理解安全风险并需要该能力时使用：

```powershell
docker compose -f docker-compose.yml -f docker-compose.restart-tools.yml up -d --force-recreate mcp-monitor api
```

该工具仍受应用层管理员审批和容器白名单限制，且禁止重启 `aiops-api` 与 `aiops-mcp-monitor` 控制面容器。
