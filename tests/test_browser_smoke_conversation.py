"""Browser Smoke 的 Conversation 工程替身生命周期测试。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from browser_smoke_app import (
    BrowserSmokeConversationAgent,
    BrowserSmokeConversationStore,
    BrowserSmokeConversationUnitOfWork,
)
from position_pilot.application.conversation_service import (
    ConversationService,
    ConversationThreadNotFound,
    ConversationTurnStatus,
)

NOW = datetime(2026, 8, 29, 8, 0, tzinfo=UTC)
ACCOUNT_A = UUID("10000000-0000-4000-8000-000000000001")
ACCOUNT_B = UUID("10000000-0000-4000-8000-000000000002")
PORTFOLIO_USER = UUID("20000000-0000-4000-8000-000000000001")


def test_browser_smoke_conversation_is_account_owned_and_explicitly_fake() -> None:
    """替身只能验证 UI 生命周期，仍保持真实 Service 的 Owner/Citation 边界。"""

    store = BrowserSmokeConversationStore()
    service = ConversationService(
        lambda: BrowserSmokeConversationUnitOfWork(store),
        agent=BrowserSmokeConversationAgent(),
        clock=lambda: NOW,
    )
    thread = service.start_thread(ACCOUNT_A)
    completion = service.ask(
        ACCOUNT_A,
        thread.id,
        portfolio_user_id=PORTFOLIO_USER,
        question="GOOG 怎么分析？",
        client_request_id=uuid4(),
        expected_thread_revision=thread.revision,
    )

    assert completion.turn.status is ConversationTurnStatus.COMPLETED
    assert completion.assistant_message is not None
    assert completion.sources[0].source_id is not None
    assert f"[source:{completion.sources[0].source_id}]" in completion.assistant_message.content
    assert completion.warnings == ("ENGINEERING_SMOKE_FAKE_AGENT",)
    assert len(service.history(ACCOUNT_A, thread.id).messages) == 2
    with pytest.raises(ConversationThreadNotFound):
        service.history(ACCOUNT_B, thread.id)

    service.delete_thread(ACCOUNT_A, thread.id)
    with pytest.raises(ConversationThreadNotFound):
        service.history(ACCOUNT_A, thread.id)
