# 内存使用率过高告警处理 Runbook

## 适用场景与检索关键词

- 告警：`HighMemoryUsage`、内存持续超过 85%、容器接近 memory limit。
- 关键词：OOM、OOMKilled、OutOfMemoryError、memory leak、RSS、working set、heap、off-heap、swap、GC overhead。
- 适用于 Linux 主机、容器和 JVM 服务，也可用于区分业务缓存增长与真实内存泄漏。

## 告警定义与影响

内存连续 5 分钟超过 80% 可预警，超过 90% 或逼近容器 limit 应视为严重。可能影响包括频繁 GC、swap、OOM Kill、实例重启和请求失败。Linux page cache、JVM 已提交堆和实际工作集口径不同，不能混为一谈。

## 排查前必须确认的信息

1. 服务、实例、运行时、容器内存 limit 和告警时间范围。
2. 内存是持续缓慢增长、阶梯增长还是瞬时上涨后回落。
3. 重启次数、OOM 记录、Full GC、流量和大文件任务是否同期变化。
4. 指标口径是主机 used、容器 working set、进程 RSS 还是 JVM heap used。
5. 是否刚发生发布、缓存预热、批处理或数据导入。

## 证据驱动的排查流程

### 1. 确认活动告警

使用 `get_current_time` 和 `query_prometheus_alerts` 确认当前告警状态、影响实例和持续时间。没有活动告警时，不得把历史描述写成当前事实。

### 2. 查询内存趋势

使用 `query_memory_metrics` 比较平均值、峰值、重启前后变化和实例差异。持续单调增长比单次高水位更支持泄漏判断。

### 3. 关联 CPU 和日志

使用 `query_cpu_metrics` 检查是否有 GC 引起的 CPU 抖动。再通过 `search_topic_by_service_name`、`get_topic_info_by_name` 和 `search_log` 查询 OOM、GC overhead、allocation failure、large object、cache、upload 和 batch job。

### 4. 人工补充运行时证据

```bash
free -h
ps -eo pid,cmd,rss,vsz,%mem --sort=-rss | head -n 20
cat /proc/<pid>/status
jstat -gcutil <pid> 1000 10
jcmd <pid> GC.heap_info
```

堆转储可能造成停顿并占用大量磁盘，只能由人工确认空间和影响后执行，不应由 Agent 自动触发。

## 现象、证据与结论判断表

| 现象 | 必要证据 | 可支持的判断 |
|---|---|---|
| Full GC 后堆占用仍持续升高 | GC 前后堆曲线、对象保留证据 | 堆内存泄漏可能性高 |
| RSS 上升但 JVM heap 平稳 | 进程 RSS、direct buffer、线程数 | 堆外内存或线程栈增长 |
| 流量上涨时内存升高，流量下降后回落 | QPS 与 working set 时间相关 | 请求对象或正常弹性使用 |
| 缓存预热后保持稳定高水位 | 缓存日志、命中率、容量配置 | 缓存容量设置导致，不一定泄漏 |
| 内存逼近 limit 后容器重启 | OOMKilled、exit code 137、limit | 容器限制或真实 OOM |
| 主机 used 高但 available 充足 | page cache 和 available 指标 | Linux 缓存，不属于紧急内存耗尽 |

## 常见原因与处理方案

### 堆内存泄漏

先保留 GC 日志和堆转储，再通过对象支配树定位长期持有引用。短期可滚动重启释放内存，长期必须修复对象生命周期；重启不是根治措施。

### 堆外内存或线程数量失控

检查 direct buffer、native memory、线程数和线程栈大小。限制并发、修复线程泄漏，并按证据调整直接内存或线程栈配置。

### 缓存或批处理容量过大

核对缓存上限、TTL、淘汰策略以及批次大小。优先减小批次并改为流式处理，避免简单扩大堆掩盖问题。

### 容器 limit 或 JVM 参数不匹配

确认堆、堆外、线程栈和本地库总和低于容器 limit，并预留安全空间。调整参数前应通过压测验证，而不是只增加最大堆。

## 分级处置与风险控制

- **观察级**：内存高但稳定、available 充足、无 GC 或错误影响，继续观察趋势。
- **缓解级**：暂停大批处理、降低并发、缩小缓存或扩容实例。
- **高风险级**：滚动重启前先保存必要证据并确认其他实例容量；调用 `restart_service` 必须经过人工审批。
- 已出现 OOMKilled、连续 Full GC、swap 抖动或多实例逼近 limit 时，立即升级人工处理。

## 修复验证

1. 内存使用回落并在 30 分钟内保持稳定，不再单调增长。
2. Full GC 频率、停顿时间和 CPU 恢复到基线。
3. 无新增 OOM、OOMKilled、GC overhead 或实例重启记录。
4. 核心请求成功率和延迟正常，缓存命中率未因过度清理明显下降。
5. 若调整 limit 或堆参数，验证峰值负载下仍保留安全余量。

## 常见误判

- 不能仅凭 Linux used 百分比判断内存耗尽，应同时查看 available、page cache 和 swap。
- JVM 堆高不等于泄漏，必须观察 Full GC 后基线是否持续抬升。
- 重启后内存下降只能说明进程状态被清空，不能证明根因已经解决。
- 容器 OOMKilled 既可能是泄漏，也可能是 limit 过低或并发突增。

## 预防措施

- 同时监控 working set、RSS、heap、Full GC、swap 和容器重启数。
- 为缓存、队列、批处理和文件上传设置容量上限。
- JVM 服务保留 GC 日志并建立正常负载基线。
- 发布前进行长稳压测，而不仅是短时峰值压测。

## 关联告警

- `FrequentFullGC`
- `ContainerOOMKilled`
- `HighCPUUsage`
- `SlowResponse`
- `ContainerRestartLoop`
