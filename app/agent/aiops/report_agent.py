"""Report Agent: turns collected evidence into the final report."""

from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_qwq import ChatQwen
from langgraph.config import get_stream_writer
from loguru import logger

from app.config import config

from .contracts import AgentMessage, AgentRole, MessageType
from .state import PlanExecuteState

report_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是 Report Agent。仅依据输入的诊断证据生成结构化 Markdown 故障报告。
报告必须包含执行摘要、关键证据、根因判断、风险和处理建议。
不得编造证据；失败的步骤必须明确披露。"""),
    ("user", "原始任务：{task}\n\n诊断证据：{evidence}"),
])


class ReportAgent:
    role = AgentRole.REPORT

    async def generate(self, state: PlanExecuteState) -> dict[str, Any]:
        evidence = state.get("evidence", [])
        try:
            llm = ChatQwen(model=config.rag_model, api_key=config.dashscope_api_key, temperature=0)
            chain = report_prompt | llm | StrOutputParser()
            writer = get_stream_writer()
            chunks = []
            async for chunk in chain.astream({"task": state.get("input", ""), "evidence": evidence}):
                if not chunk:
                    continue
                chunks.append(chunk)
                writer({"type": "report_chunk", "stage": "report_streaming", "data": chunk})
            markdown = "".join(chunks).strip()
            if not markdown:
                raise ValueError("Report Agent 返回空报告")
        except Exception as exc:
            logger.error(f"Report Agent 生成报告失败: {exc}")
            lines = [f"- **{item.get('objective', '未知步骤')}**：{item.get('summary', '')}" for item in evidence]
            markdown = "# 故障诊断报告\n\n## 已收集证据\n" + ("\n".join(lines) or "暂无有效证据")
            try:
                get_stream_writer()({"type": "report_replace", "stage": "report_streaming", "data": markdown})
            except RuntimeError:
                pass

        message = AgentMessage.create(
            correlation_id=state.get("correlation_id", "default"),
            sender=self.role,
            recipient=AgentRole.ORCHESTRATOR,
            message_type=MessageType.REPORT_CREATED,
            payload={"markdown": markdown},
        )
        return {"response": markdown, "agent_messages": [message.model_dump(mode="json")], "next_agent": "complete"}
