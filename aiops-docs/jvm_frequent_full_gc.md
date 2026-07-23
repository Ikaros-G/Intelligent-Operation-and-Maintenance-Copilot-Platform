# JVM Full GC 频繁处理 Runbook

## 适用场景与检索关键词

- 告警：`FrequentFullGC`、GC 停顿时间过长、老年代持续高位。
- 关键词：Full GC、stop-the-world、GC overhead limit exceeded、allocation failure、promotion failed、concurrent mode failure、Metaspace。
- 适用于 JVM 应用；非 JVM 服务的内存问题应使用内存高 Runbook。

## 告警定义与影响

Full GC 次数、总停顿时间或老年代占用持续超过基线时应告警。频繁 Full GC 会造成 stop-the-world、延迟尖峰、CPU 上升和吞吐下降，严重时触发 OOM。一次发布或显式 GC 不足以证明存在持续问题。

## 排查前必须确认的信息

1. 服务、实例、JDK 版本、GC 算法、堆大小和容器 memory limit。
2. Full GC 次数、间隔、停顿时间和回收前后堆占用。
3. CPU、内存、QPS、请求延迟和 OOM 是否同步变化。
4. 是否刚发布、缓存预热、批处理、大文件处理或调整 JVM 参数。
5. GC 日志是否完整，时间戳是否和告警窗口一致。

## 证据驱动的排查流程

### 1. 查询活动告警和资源趋势

使用 `get_current_time`、`query_prometheus_alerts` 确认告警，使用 `query_cpu_metrics`、`query_memory_metrics` 对比 Full GC 前后的资源变化。

### 2. 查询应用和 GC 日志

使用 `search_topic_by_service_name`、`get_topic_info_by_name` 找到日志主题，再用 `search_log` 查询 Full GC、allocation failure、promotion failed、GC overhead、Metaspace、OutOfMemoryError 和 safepoint。

### 3. 比较回收效果

记录每次 Full GC 前后老年代或堆占用。回收后基线持续抬升更支持泄漏；回收效果明显但很快再次填满，更支持堆过小、分配速率过高或大对象问题。

### 4. 人工 JVM 检查

```bash
jstat -gcutil <pid> 1000 20
jcmd <pid> GC.heap_info
jcmd <pid> VM.flags
jcmd <pid> VM.native_memory summary
```

堆转储和强制 GC 可能造成停顿或磁盘压力，必须由人工评估后执行。

## 现象、证据与结论判断表

| 现象 | 必要证据 | 可支持的判断 |
|---|---|---|
| Full GC 后老年代基线持续抬升 | 多次 GC 前后占用、对象证据 | 堆泄漏可能性高 |
| 回收效果好但很快再次 Full GC | 分配速率、堆大小、QPS | 堆过小或对象分配过快 |
| promotion failed | 年轻代、老年代余量、对象年龄 | 晋升空间不足 |
| Metaspace OOM | 类加载数量、Metaspace 使用 | 类加载器泄漏或元空间不足 |
| GC 与大批处理时间一致 | 任务日志、对象分配、时间线 | 大对象或批次过大 |
| JVM heap 正常但 RSS 高 | native memory、线程数 | 堆外问题，不是 Full GC 根因 |

## 常见原因与处理方案

### 内存泄漏

保留 GC 日志和堆转储，分析对象支配树、类加载器和引用链。滚动重启只能缓解，必须修复对象生命周期。

### 堆配置与容器限制不匹配

确保堆、Metaspace、direct memory、线程栈和本地库总和低于容器 limit。调整堆前需长稳压测。

### 大对象、批处理或高分配速率

缩小批次、改为流式处理、减少临时对象和重复序列化。只更换 GC 算法不能解决无限分配。

### GC 参数或算法不适配

根据 JDK、堆大小和延迟目标评估参数，先在压测环境验证；避免复制其他服务的参数模板。

## 分级处置与风险控制

- 偶发 Full GC 且停顿可接受：观察趋势并保留日志。
- 延迟受影响：暂停大批处理、降低并发或扩容健康实例。
- 滚动重启前保留必要证据；调用 `restart_service` 必须人工审批。
- 连续 Full GC、GC overhead、OOM 或全部实例同时受影响时，立即升级人工 JVM 负责人。

## 修复验证

1. Full GC 频率和总停顿时间恢复基线。
2. GC 后老年代占用稳定，不再持续抬升。
3. P95/P99 延迟、CPU 和吞吐恢复。
4. 无新增 GC overhead、promotion failed 或 OOM。
5. 在峰值负载和一个完整批处理周期内保持稳定。

## 常见误判

- 不能仅凭日志中出现一次 Full GC 判断 GC 异常，需比较频率、停顿和回收效果。
- CPU 高可能由 GC 引起，也可能是业务计算，必须对齐时间线。
- 增大堆会延后 OOM，也可能增加停顿时间，不能替代泄漏修复。
- RSS 高而 heap 正常时应检查堆外内存，不应只调 GC。

## 预防措施

- 保留并集中采集 GC 日志，监控次数、停顿、分配和晋升速率。
- 发布前进行峰值和长稳压测。
- 为缓存、批处理、大文件和对象队列设置容量边界。
- JVM 参数纳入版本管理，并记录变更前后基线。

## 关联告警

- `HighMemoryUsage`
- `HighCPUUsage`
- `SlowResponse`
- `ContainerOOMKilled`
- `ContainerRestartLoop`
