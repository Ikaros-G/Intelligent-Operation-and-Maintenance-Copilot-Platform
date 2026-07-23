# AIOps 运维知识库 Runbook 扩充设计

## 目标

面向项目演示补充一组可检索、可执行、证据驱动的运维 Runbook。用户输入故障现象后，RAG 应能召回与症状匹配的排障步骤；Agent 必须先收集指标和日志证据，再给出原因判断与处置建议，不能仅凭用户描述直接确认故障类型。

## 内容范围

完善以下 5 篇现有文档：

1. `cpu_high_usage.md`
2. `memory_high_usage.md`
3. `disk_high_usage.md`
4. `service_unavailable.md`
5. `slow_response.md`

新增以下 8 篇文档：

1. `high_error_rate.md`
2. `database_slow_query.md`
3. `database_connection_pool_exhausted.md`
4. `redis_connection_failure.md`
5. `container_restart_loop.md`
6. `network_dns_failure.md`
7. `jvm_frequent_full_gc.md`
8. `thread_pool_exhausted.md`

不扩展 Kubernetes、消息队列、证书管理和云厂商专属操作，避免演示知识面过宽且缺少项目工具支撑。

## 文档结构

每篇 Runbook 使用相同的一级和二级标题结构，便于 MarkdownHeaderTextSplitter 按主题生成稳定分片：

1. 适用场景与检索关键词
2. 告警定义与影响
3. 排查前必须确认的信息
4. 证据驱动的排查流程
5. 现象、证据与结论判断表
6. 常见原因与处理方案
7. 分级处置与风险控制
8. 修复验证
9. 常见误判
10. 预防措施
11. 关联告警

单个二级主题应尽量保持语义完整。内容较长时使用三级标题细分，但不依赖三级标题形成独立检索上下文。

## 工具映射

Runbook 只引用项目中真实存在的工具：

| 诊断目的 | 工具 |
|---|---|
| 获取当前时间 | `get_current_time` / `get_current_timestamp` |
| 查询活动告警 | `query_prometheus_alerts` |
| 查询 CPU 指标 | `query_cpu_metrics` |
| 查询内存指标 | `query_memory_metrics` |
| 根据服务发现日志主题 | `search_topic_by_service_name` |
| 获取日志主题信息 | `get_topic_info_by_name` |
| 查询日志 | `search_log` |
| 服务重启 | `restart_service`，仅在审批后执行 |

磁盘、数据库、Redis、网络、JVM 和线程池没有独立指标工具时，文档应明确通过应用日志、系统日志及人工命令补充证据，不虚构工具调用结果。

## 安全边界

- `restart_service` 属于高风险操作，必须在证据确认、影响评估和人工审批后执行。
- 删除文件、清空日志、终止进程、修改连接池、扩容和回滚只作为建议，不描述为 Agent 已自动执行。
- 命令默认采用只读检查；破坏性命令必须标注风险、备份要求和回滚条件。
- 不使用固定地域、固定日志主题、虚构联系人或内部文档链接。

## 检索设计

每篇文档开头列出中文症状、常见英文错误、告警名和相关组件名称。例如数据库连接池文档包含 `Too many connections`、`connection pool exhausted`、`timeout waiting for connection` 等关键词，以提高用户自然语言与日志原文的召回率。

相近主题必须说明边界。例如慢响应文档负责端到端延迟定位，数据库慢查询文档负责 SQL 执行证据，连接池耗尽文档负责等待连接和连接泄漏证据，避免检索结果互相替代。

## 验收标准

1. `aiops-docs` 最终包含 13 个 Markdown 文件。
2. 所有文件均为 UTF-8，标题结构完整，无空章节或占位符。
3. 不再出现不存在的 `query_logs` 工具。
4. 所有自动工具调用名称与项目实现一致。
5. 每篇文档至少包含一组“不能仅凭现象下结论”的反例。
6. 每篇文档包含修复验证标准和需要升级人工处理的条件。
7. 使用项目现有文档切分器验证所有文件都能产生非空分片。
8. 抽查典型问题，确认 CPU、内存、5xx、数据库、Redis、容器、DNS、GC 和线程池主题能召回对应文档。

