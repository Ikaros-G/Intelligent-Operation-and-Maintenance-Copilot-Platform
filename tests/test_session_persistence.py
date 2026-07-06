from langchain_core.messages import HumanMessage

from app.services.rag_agent_service import RagAgentService


class FakeAsyncCheckpointer:
    def __init__(self):
        self.deleted = None

    async def aget(self, config):
        return {"channel_values": {"messages": [HumanMessage(content="hello")]}}

    async def adelete_thread(self, session_id):
        self.deleted = session_id


async def test_session_history_uses_async_checkpointer_contract():
    service = RagAgentService.__new__(RagAgentService)
    service.checkpointer = FakeAsyncCheckpointer()

    history = await service.get_session_history("session-1")

    assert history[0]["role"] == "user"
    assert history[0]["content"] == "hello"


async def test_clear_session_uses_async_checkpointer_contract():
    service = RagAgentService.__new__(RagAgentService)
    service.checkpointer = FakeAsyncCheckpointer()

    assert await service.clear_session("session-1")
    assert service.checkpointer.deleted == "session-1"
