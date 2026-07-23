# 网络连接与 DNS 解析异常处理 Runbook

## 适用场景与检索关键词

- 告警：`DNSResolutionFailure`、`NetworkConnectionFailure`、下游连接异常。
- 关键词：DNS、NXDOMAIN、SERVFAIL、name resolution、connection refused、connection reset、no route to host、packet loss、connect timeout。
- 适用于服务间调用、域名解析和端口连接问题；应用执行超时但网络阶段正常时应转入慢响应 Runbook。

## 告警定义与影响

DNS 失败率、连接失败率或建连耗时持续超过基线应告警。网络错误可能发生在解析、路由、防火墙、端口监听、TLS 或连接复用阶段。`connection refused` 与 connect timeout 的含义不同，必须保留原始错误。

## 排查前必须确认的信息

1. 调用方、目标域名/IP、端口、协议、环境和时间窗口。
2. 错误原文以及发生在 DNS、建连、TLS、读取还是连接复用阶段。
3. 是单实例、单节点、单地域还是所有调用方受影响。
4. 是否发生 DNS、证书、负载均衡、防火墙、服务发布或网络策略变更。
5. 目标服务是否健康、端口是否监听、直连 IP 是否成功。

## 证据驱动的排查流程

### 1. 查询活动告警和服务资源

使用 `get_current_time`、`query_prometheus_alerts` 查找调用方、目标服务和网络相关告警。使用 `query_cpu_metrics`、`query_memory_metrics` 排除目标服务因资源耗尽无法接受连接。

### 2. 查询调用日志

使用 `search_topic_by_service_name`、`get_topic_info_by_name` 定位调用方日志，再用 `search_log` 查询 NXDOMAIN、SERVFAIL、connection refused、connection reset、connect timeout、read timeout、no route 和目标地址。

### 3. 人工分阶段测试

```bash
nslookup <domain>
dig <domain> A
getent hosts <domain>
curl -v --connect-timeout 3 https://<domain>/health
nc -vz <host> <port>
```

Windows 可使用：

```powershell
Resolve-DnsName <domain>
Test-NetConnection <host> -Port <port>
```

### 4. 对比多位置结果

从至少两个调用实例检查解析结果和连通性。单实例失败更支持本地缓存、节点网络或连接池问题；全部失败更支持目标服务、DNS 或网络策略问题。

## 现象、证据与结论判断表

| 现象 | 必要证据 | 可支持的判断 |
|---|---|---|
| NXDOMAIN | 多次解析、域名配置、不同 DNS 服务器 | 域名不存在或记录未生效 |
| SERVFAIL 或解析超时 | DNS 服务器响应、多实例对比 | DNS 服务或网络异常 |
| connection refused | IP 可达、目标端口未监听 | 服务未监听或主动拒绝 |
| connect timeout | 路由、防火墙、目标负载 | 网络丢弃、路由或目标过载 |
| connection reset | 双端日志、连接持续时间 | 对端或中间设备重置连接 |
| 域名失败但 IP 直连成功 | 解析结果、直连测试 | DNS 或域名配置问题 |

## 常见原因与处理方案

### DNS 记录或缓存异常

核对记录、TTL、搜索域和生效范围，避免通过长期 hosts 修改掩盖配置问题。缓存刷新前评估对现有连接的影响。

### 目标服务未监听或健康后端为空

检查进程、端口、健康检查和负载均衡后端。只有目标服务确实异常时才进入服务恢复流程。

### 防火墙、路由或安全策略变更

对比变更时间和受影响网段，由网络人员检查规则命中。不要为了验证临时关闭全部防火墙。

### 连接复用和客户端池问题

旧连接、连接池耗尽或 NAT 端口压力可能表现为 reset/timeout。检查连接生命周期、重试和池状态。

## 分级处置与风险控制

- 单实例问题：隔离实例并检查本地 DNS 缓存、连接池和节点网络。
- 多实例问题：暂停相关网络或 DNS 变更，启用已验证的备用地址或降级。
- 修改 DNS、路由、防火墙和负载均衡配置必须人工审批并保留回滚值。
- 核心服务跨区域不可达、解析全面失败或错误持续扩大时，立即升级人工网络负责人。

## 修复验证

1. 多个调用实例解析结果一致且符合预期。
2. DNS、建连、TLS 和请求阶段均成功，耗时恢复基线。
3. connection refused、reset、timeout 和 NXDOMAIN 日志停止增长。
4. 目标服务健康，负载均衡后端数量正常。
5. 观察至少一个 DNS TTL 周期，确认缓存收敛。

## 常见误判

- 不能仅凭 ping 失败认定网络不可达，很多环境禁止 ICMP 但业务端口正常。
- connection refused 表示目标明确拒绝，和网络静默丢包导致的 timeout 不同。
- DNS 解析成功不代表目标端口或应用可用。
- IP 直连成功只能定位 DNS 方向，不能作为长期绕过服务发现的方案。

## 预防措施

- 分别监控 DNS、connect、TLS、首字节和总耗时。
- 网络和 DNS 配置采用审计、灰度和快速回滚。
- 客户端设置合理超时、有限重试、连接最大生命周期和熔断。
- 保留调用方、目标地址、解析结果和 trace ID 日志。

## 关联告警

- `ServiceUnavailable`
- `HighErrorRate`
- `SlowResponse`
- `RedisUnavailable`
- `DatabaseUnavailable`
