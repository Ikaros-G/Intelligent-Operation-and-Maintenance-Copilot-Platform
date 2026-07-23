# 线程池耗尽与请求堆积处理 Runbook

## 适用场景与检索关键词

- 告警：`ThreadPoolExhausted`、工作线程全部忙、队列持续增长。
- 关键词：RejectedExecutionException、thread pool exhausted、queue full、active threads、pending tasks、request queue timeout、线程池、请求堆积。
- 适用于 Web、异步任务和业务执行线程池；数据库连接池等待应使用数据库连接池 Runbook。

## 告警定义与影响

活跃线程长期等于最大线程数、任务队列持续增长、拒绝执行或排队时间超标均应告警。线程池耗尽会导致请求尚未执行业务逻辑就超时，进一步触发客户端重试和级联拥塞。

## 排查前必须确认的信息

1. 服务、实例、线程池名称、核心/最大线程数、队列容量和拒绝策略。
2. active、queue、completed、rejected 和任务执行时间趋势。
3. 哪类任务占用线程，是否等待数据库、Redis、外部 API、锁或 I/O。
4. 是否有流量增长、批处理、发布或超时重试配置变化。
5. 请求排队时间、实际执行时间和下游耗时是否分别记录。

## 证据驱动的排查流程

### 1. 查询告警和资源

使用 `get_current_time`、`query_prometheus_alerts` 确认告警范围；使用 `query_cpu_metrics`、`query_memory_metrics` 判断线程繁忙是计算饱和、等待阻塞还是线程数量导致的内存压力。

### 2. 查询线程池和请求日志

使用 `search_topic_by_service_name`、`get_topic_info_by_name` 查找主题，再用 `search_log` 查询 RejectedExecutionException、queue full、task timeout、pool active、lock wait、upstream timeout 和 request ID。

### 3. 分析任务耗时和等待点

按任务类型聚合执行时间，比较排队时间与执行时间。排队长说明容量不足或任务执行过慢；执行时间长需继续定位数据库、网络、锁或 CPU。

### 4. 人工采集线程栈

```bash
jcmd <pid> Thread.print
jstack <pid>
ps -L -p <pid> -o pid,tid,pcpu,stat,comm
```

多次间隔采样比单份线程栈更可靠。线程栈可能包含业务参数，分享前需脱敏。

## 现象、证据与结论判断表

| 现象 | 必要证据 | 可支持的判断 |
|---|---|---|
| active=max 且 queue 持续增长 | 线程池指标、任务执行时间 | 线程池容量不足或任务变慢 |
| 大量线程等待同一外部调用 | 线程栈、upstream timeout | 下游阻塞 |
| 大量线程 BLOCKED 在同一锁 | 多次线程栈、锁持有者 | 锁竞争或死锁风险 |
| CPU 满且线程多为 RUNNABLE | CPU 指标、线程 CPU、栈 | 计算密集任务饱和 |
| RejectedExecutionException 突增 | 拒绝计数、队列和 QPS | 队列已满或线程池关闭 |
| queue 高但 active 未到上限 | 线程池配置、任务调度状态 | 配置错误或执行器异常 |

## 常见原因与处理方案

### 慢下游占用线程

确认数据库、Redis 或外部 API 耗时，设置超时、熔断和隔离线程池。无限等待和无限重试会耗尽线程。

### 锁竞争或死锁

通过多次线程栈定位锁持有者和等待链，缩小锁粒度或修复锁顺序。终止进程前必须保留现场。

### 线程池配置与负载不匹配

结合任务是 CPU 密集还是 I/O 密集评估线程数和队列。只增加线程可能加剧 CPU 切换、内存使用和下游压力。

### 批处理或重试任务挤占在线请求

隔离在线与离线线程池，限制批处理并发，对重试设置次数、退避和抖动。

## 分级处置与风险控制

- 队列短时上涨后回落：观察并保留慢任务样本。
- 队列持续增长：限流、暂停批处理、熔断慢下游或扩容健康实例。
- 修改线程数、队列容量和拒绝策略应灰度发布并准备回滚。
- 如需重启清空失控线程，调用 `restart_service` 必须人工审批且先保留线程栈。
- 核心线程池拒绝大量请求、疑似死锁或所有实例队列增长时，立即升级人工处理。

## 修复验证

1. active、queue、rejected 和排队时间恢复到基线。
2. 任务执行时间和下游耗时稳定。
3. RejectedExecutionException 和 request queue timeout 不再新增。
4. CPU、内存和线程数量保留余量。
5. 在峰值 QPS 下验证队列不会持续增长。

## 常见误判

- 不能仅凭线程数多认定线程池耗尽，必须查看 active、queue 和 rejected。
- active 达到最大值可能是正常峰值，持续队列增长才说明无法及时处理。
- 增加线程数不一定提高吞吐，CPU 密集任务可能因切换变慢。
- 请求超时可能发生在连接池或网络阶段，不一定占用了业务线程。

## 预防措施

- 监控线程池 active、queue、completed、rejected 和任务耗时。
- 在线请求、批处理和不同依赖使用隔离线程池。
- 所有阻塞调用设置超时、有限重试和熔断。
- 定期采集峰值负载下的线程栈和容量基线。

## 关联告警

- `SlowResponse`
- `HighErrorRate`
- `HighCPUUsage`
- `DatabaseConnectionPoolExhausted`
- `ServiceUnavailable`
