# Docker 容器频繁重启处理 Runbook

## 适用场景与检索关键词

- 告警：`ContainerRestartLoop`、容器重启次数持续增加、实例反复上下线。
- 关键词：restart loop、CrashLoop、OOMKilled、exit code 137、exit code 143、health check failed、Back-off restarting、容器启动失败。
- 适用于 Docker 容器和容器化服务；计划内滚动发布造成的一次正常重启不属于故障。

## 告警定义与影响

容器在短时间内连续重启、无法保持就绪或重启次数异常增长应触发告警。频繁重启会造成容量波动、请求失败、缓存反复预热和日志现场丢失。退出码只能提供方向，不能单独证明根因。

## 排查前必须确认的信息

1. 服务、容器名、镜像版本、实例、重启次数和首次重启时间。
2. 容器退出码、OOMKilled 标记、启动日志和健康检查结果。
3. 是否处于计划发布、配置更新、宿主机维护或自动扩缩容期间。
4. CPU、内存 limit、挂载、环境变量和依赖服务状态。
5. 重启由 Docker 策略、编排平台、健康检查还是人工操作触发。

## 证据驱动的排查流程

### 1. 确认活动告警和影响范围

使用 `get_current_time`、`query_prometheus_alerts` 确认告警和受影响实例。检查是否只有一个版本或一个节点上的容器异常。

### 2. 查询资源趋势

使用 `query_memory_metrics` 检查重启前是否逼近 memory limit，使用 `query_cpu_metrics` 检查启动阶段是否 CPU 限流或异常打满。

### 3. 查询启动和退出日志

通过 `search_topic_by_service_name`、`get_topic_info_by_name` 找到日志主题，再用 `search_log` 查询 OOMKilled、OutOfMemoryError、configuration error、permission denied、bind failed、health check、shutdown 和 signal。

### 4. 人工检查容器元数据

```bash
docker ps -a --filter name=<service>
docker inspect <container>
docker logs --tail 200 <container>
docker events --since 30m --filter container=<container>
```

应保存首次失败日志，而不是只查看最后一次重启后的输出。

## 现象、证据与结论判断表

| 现象 | 必要证据 | 可支持的判断 |
|---|---|---|
| exit code 137 且 OOMKilled=true | inspect、内存趋势、limit | 容器超过内存限制 |
| exit code 143 且存在停止事件 | signal、发布或人工操作记录 | 正常 SIGTERM 或外部终止 |
| 启动后立即退出并有配置异常 | 启动日志、版本和配置变更 | 配置或启动参数错误 |
| 进程正常但探针连续失败 | 探针路径、超时、直连请求 | 健康检查配置或启动过慢 |
| 仅某宿主机上的容器重启 | 节点事件、资源和存储错误 | 宿主机局部问题 |
| 依赖未就绪后进程主动退出 | 依赖日志、重试策略 | 启动依赖和重试策略问题 |

## 常见原因与处理方案

### OOMKilled 或资源限制过低

结合 memory limit、工作集和应用 OOM 日志确认。短期降低并发或扩容，长期修复泄漏、批处理或 JVM 参数；不要只无限提高 limit。

### 启动配置或镜像回归

对比正常版本的环境变量、挂载、入口命令和依赖地址。若只影响新镜像，暂停发布并评估回滚。

### 健康检查配置错误

区分存活与就绪探针，核对启动宽限期、路径、端口和超时。探针过严会杀死仍在正常启动的进程。

### 依赖故障或重试策略不当

应用应在依赖短时不可用时有限重试或保持未就绪，而不是立即退出并形成重启风暴。

## 分级处置与风险控制

- 一次计划内重启且服务健康：记录原因，无需干预。
- 单实例循环重启：摘除实例、保留日志，确认其他实例容量。
- 多实例循环重启：暂停发布或自动扩缩容，优先恢复稳定版本。
- 直接重启无法解决已经存在的重启循环；如需调用 `restart_service`，必须人工审批并说明预期作用。
- 全部实例无法就绪、OOM 扩散或宿主机异常时，立即升级人工处理。

## 修复验证

1. 重启次数在 30 分钟内不再增长。
2. 容器保持 running 且健康检查连续通过。
3. CPU、内存和 limit 保留安全余量。
4. 启动、依赖和探针错误不再出现。
5. 真实业务请求成功，缓存预热和连接重建没有压垮依赖。

## 常见误判

- 不能仅凭 restart count 大于零认定存在重启循环，可能是历史发布累积值。
- exit code 137 常见于 OOMKilled，但也可能由外部 SIGKILL，需要 inspect 证据。
- exit code 143 通常是 SIGTERM，可能属于正常滚动停止。
- 健康检查失败不一定是应用崩溃，也可能是探针路径或超时设置错误。

## 预防措施

- 监控重启速率而不只是累计次数。
- 为启动、退出和信号处理记录结构化日志。
- 合理设置资源 request/limit、启动宽限期和健康检查。
- 发布前验证配置、挂载、依赖和优雅退出流程。

## 关联告警

- `ContainerOOMKilled`
- `HighMemoryUsage`
- `HealthCheckFailed`
- `ServiceUnavailable`
- `HighCPUUsage`
