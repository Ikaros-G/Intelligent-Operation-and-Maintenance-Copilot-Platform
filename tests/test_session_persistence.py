from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.services.rag_agent_service import RagAgentService


class FakeAsyncCheckpointer:
    def __init__(self):
        self.deleted = None

    async def aget(self, config):
        return {"channel_values": {"messages": [HumanMessage(content="hello")]}}

    async def adelete_thread(self, session_id):
        self.deleted = session_id


class FakeToolConversationCheckpointer:
    async def aget(self, config):
        return {
            "channel_values": {
                "messages": [
                    SystemMessage(content="system prompt"),
                    HumanMessage(content="我的内存占用率很高"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "query_prometheus_alerts",
                                "args": {},
                                "id": "call-1",
                                "type": "tool_call",
                            }
                        ],
                    ),
                    ToolMessage(
                        content='{"success": true, "alerts": []}',
                        tool_call_id="call-1",
                    ),
                    AIMessage(content="## 最终回答\n\n当前没有活跃告警。"),
                ]
            }
        }


async def test_session_history_uses_async_checkpointer_contract():
    service = RagAgentService.__new__(RagAgentService)
    service.checkpointer = FakeAsyncCheckpointer()

    history = await service.get_session_history("session-1")

    assert history[0]["role"] == "user"
    assert history[0]["content"] == "hello"


async def test_session_history_excludes_internal_tool_messages():
    service = RagAgentService.__new__(RagAgentService)
    service.checkpointer = FakeToolConversationCheckpointer()

    history = await service.get_session_history("session-with-tools")

    assert [(item["role"], item["content"]) for item in history] == [
        ("user", "我的内存占用率很高"),
        ("assistant", "## 最终回答\n\n当前没有活跃告警。"),
    ]


async def test_clear_session_uses_async_checkpointer_contract():
    service = RagAgentService.__new__(RagAgentService)
    service.checkpointer = FakeAsyncCheckpointer()

    assert await service.clear_session("session-1")
    assert service.checkpointer.deleted == "session-1"
