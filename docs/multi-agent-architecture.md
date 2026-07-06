# AIOps Multi-Agent 架构

诊断工作流由三个职责独立的 Agent 组成：

1. **Planner Agent**：读取任务和历史证据，生成初始计划，并在每个诊断步骤后决定继续、重新规划或转交报告。
2. **Diagnosis Agent**：一次只执行一个计划步骤，通过本地工具和 MCP 工具采集真实证据，不负责修改诊断目标或生成最终结论。
3. **Report Agent**：只读取原始任务和结构化证据，生成最终 Markdown 故障报告，不直接调用运维工具。

工作流拓扑：

```text
Planner Agent
     |
     v
Diagnosis Agent <----+
     |               |
     v               |
Planner Review ------+
     |
     v
Report Agent
```

## 消息协议

Agent 交接统一使用 `AgentMessage` 信封：

| 字段 | 说明 |
|---|---|
| `message_id` | 单条消息的 UUID |
| `correlation_id` | 会话 ID，用于串联一次诊断的全部消息 |
| `sender` / `recipient` | 发送方与接收方角色 |
| `message_type` | 计划、执行请求、证据、计划更新、报告请求或报告 |
| `payload` | 与消息类型对应的结构化负载 |
| `created_at` | UTC 时间戳 |

协议模型位于 `app/agent/aiops/contracts.py`。所有消息都以可 JSON 序列化的形式进入 LangGraph 状态，便于后续持久化和审计。

## 共享状态协议

`PlanExecuteState` 保存以下跨 Agent 状态：

- `plan`：尚未执行的结构化 `PlanStep` 列表；
- `evidence`：Diagnosis Agent 追加的 `ExecutionEvidence`；
- `agent_messages`：不可变的消息轨迹；
- `next_agent`：Planner Agent 给出的下一跳；
- `correlation_id`：端到端诊断关联 ID；
- `response`：Report Agent 生成的最终报告。

对外 SSE 事件仍保持 `plan`、`step_complete`、`status`、`report`、`complete`，因此现有前端无需修改。
