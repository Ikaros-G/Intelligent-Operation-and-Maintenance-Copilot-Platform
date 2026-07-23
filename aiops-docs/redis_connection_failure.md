# Redis 连接失败或延迟过高处理 Runbook

## 适用场景与检索关键词

- 告警：`RedisUnavailable`、`RedisHighLatency`、缓存请求超时。
- 关键词：Redis、connection refused、timeout、READONLY、MOVED、CLUSTERDOWN、NOAUTH、hot key、big key、cache miss。
- 适用于 Redis 连接失败、命令延迟或缓存异常；应用数据库连接问题不在本 Runbook 范围内。

## 告警定义与影响

Redis 连接失败、P99 命令延迟持续超标或错误率升高会造成接口变慢、缓存穿透和数据库压力突增。Redis 错误文本可能来自网络、认证、主从切换、集群重定向或客户端池，必须按错误类型取证。

## 排查前必须确认的信息

1. 服务、Redis 实例或集群、环境和故障时间。
2. 是所有命令、特定 key、单节点还是单应用实例异常。
3. 错误文本、命令延迟、连接池等待、缓存命中率和 QPS。
4. 是否发生扩缩容、主从切换、密码轮换、网络或配置变更。
5. 缓存失败后是否有降级，以及数据库流量是否同步上涨。

## 证据驱动的排查流程

### 1. 查询活动告警和应用资源

使用 `get_current_time`、`query_prometheus_alerts` 确认 Redis、数据库和应用告警。再用 `query_cpu_metrics`、`query_memory_metrics` 检查应用是否因重试、请求堆积或本地缓存增长而异常。

### 2. 查询应用日志

使用 `search_topic_by_service_name`、`get_topic_info_by_name` 定位主题，再用 `search_log` 查询 Redis、connection refused、timeout、READONLY、MOVED、CLUSTERDOWN、NOAUTH、pool exhausted、retry 和 cache miss。

### 3. 分类错误阶段

区分 DNS/建连、认证、获取客户端连接、命令执行、集群重定向和读取超时。不同阶段的修复动作不同。

### 4. 人工 Redis 检查

由有权限的运维人员检查 ping、节点角色、复制状态、客户端数、慢日志、内存和大 key。禁止在未知 key 影响时自动删除、flush 或切换主节点。

## 现象、证据与结论判断表

| 现象 | 必要证据 | 可支持的判断 |
|---|---|---|
| connection refused | 目标地址、端口、节点状态 | 端口未监听、节点下线或网络拒绝 |
| READONLY | 节点角色、连接地址、切换时间 | 客户端连接到只读副本 |
| MOVED/CLUSTERDOWN 持续出现 | 集群槽位、客户端集群配置 | 集群拓扑或客户端支持问题 |
| 单个命令延迟高 | slowlog、命令和 key 大小 | 大 key 或高复杂度命令 |
| 所有命令延迟随 QPS 升高 | QPS、CPU、连接数、网络 | 节点过载或连接瓶颈 |
| cache miss 上升且数据库变慢 | 命中率、数据库 QPS | 缓存失效或穿透 |

## 常见原因与处理方案

### 节点不可达或网络异常

确认地址、端口、DNS 和安全策略，再检查节点状态。客户端应使用合理超时、有限重试和备用节点，避免重试风暴。

### 主从切换或集群拓扑变化

确认 READONLY、MOVED 和切换时间，修正客户端拓扑刷新和读写策略。不要在切换期间同时重启所有客户端。

### 热 key、大 key 或慢命令

通过命令统计和 slowlog 取证，拆分大 key、分散热 key、避免阻塞命令。删除 key 需要业务确认和回滚方案。

### 客户端连接池耗尽

检查池等待、连接归还和超时，修复连接泄漏。扩大池之前评估 Redis 最大客户端数。

## 分级处置与风险控制

- 单节点短时抖动：保持降级并观察自动恢复。
- 缓存大量失败：限流、保护数据库、暂停非核心高成本查询。
- flush、删除 key、主从切换、集群重分片属于高风险操作，必须人工审批。
- Redis 全面不可用、数据库因穿透接近容量上限或出现数据一致性风险时，立即升级人工处理。

## 修复验证

1. 建连和命令错误停止，P95/P99 延迟恢复。
2. 缓存命中率、连接池等待和客户端数稳定。
3. 数据库 QPS 和延迟回落，没有缓存穿透的次生影响。
4. 集群节点角色、槽位和复制状态正常。
5. 观察一个 key 过期周期，确认问题不会再次出现。

## 常见误判

- 不能仅凭 Redis timeout 认定 Redis 节点过载，超时可能发生在 DNS、网络或客户端池。
- READONLY 通常表示连接到了副本，不等于 Redis 数据损坏。
- cache miss 增加可能是业务访问模式变化，不一定是缓存服务故障。
- 扩大客户端连接池可能触发 maxclients，并不能解决慢命令。

## 预防措施

- 监控命令延迟、错误类型、连接数、命中率、内存和复制延迟。
- 对大 key、热 key、阻塞命令和慢日志建立巡检。
- 客户端支持拓扑刷新、指数退避、连接池超时和熔断。
- 缓存失效时设置数据库保护、请求合并和随机过期时间。

## 关联告警

- `RedisHighLatency`
- `RedisUnavailable`
- `DatabaseHighLoad`
- `SlowResponse`
- `HighErrorRate`
