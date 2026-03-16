import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_is_authenticated_returns_true_when_logged_in():
    from chorus.platforms.base import BaseAI
    # Create a minimal concrete subclass
    class FakePlatform(BaseAI):
        name = "fake"
        url  = "https://fake.ai"
        platform_key = "fake"
        async def submit_prompt(self, prompt): pass
        async def wait_for_response(self, timeout=90): return ""

    mock_page = MagicMock()
    mock_page.url = "https://fake.ai/chat"  # no login keywords in URL
    mock_page.query_selector = AsyncMock(return_value=None)  # no login wall element

    ai = FakePlatform(mock_page)
    result = await ai.is_authenticated()
    assert result is True


@pytest.mark.asyncio
async def test_is_authenticated_returns_false_when_login_wall():
    from chorus.platforms.base import BaseAI

    class FakePlatform(BaseAI):
        name = "fake"
        url  = "https://fake.ai"
        platform_key = "fake"
        async def submit_prompt(self, prompt): pass
        async def wait_for_response(self, timeout=90): return ""

    mock_page = MagicMock()
    mock_page.url = "https://fake.ai/login"  # login keyword in URL
    mock_page.query_selector = AsyncMock(return_value=None)

    ai = FakePlatform(mock_page)
    result = await ai.is_authenticated()
    assert result is False


def test_onboarding_state_created_if_missing(tmp_path):
    from chorus import onboarding
    state_file = tmp_path / "onboarding.json"
    state = onboarding.load_state(state_file)
    # All 8 platforms present, all pending
    for p in onboarding.ALL_PLATFORMS:
        assert state[p]["status"] == "pending"


def test_mark_completed_writes_timestamp(tmp_path):
    from chorus import onboarding
    state_file = tmp_path / "onboarding.json"
    onboarding.mark_completed("gemini", state_file)
    state = onboarding.load_state(state_file)
    assert state["gemini"]["status"] == "completed"
    assert "completed_at" in state["gemini"]


def test_mark_skipped(tmp_path):
    from chorus import onboarding
    state_file = tmp_path / "onboarding.json"
    onboarding.mark_skipped("chatgpt", state_file)
    state = onboarding.load_state(state_file)
    assert state["chatgpt"]["status"] == "skipped"


def test_needs_onboarding_true_when_all_pending(tmp_path):
    from chorus import onboarding
    state_file = tmp_path / "onboarding.json"
    assert onboarding.needs_onboarding(state_file) is True


def test_needs_onboarding_false_when_one_completed(tmp_path):
    from chorus import onboarding
    state_file = tmp_path / "onboarding.json"
    onboarding.mark_completed("gemini", state_file)
    assert onboarding.needs_onboarding(state_file) is False


@pytest.fixture
def onboarding_client(tmp_path):
    import chorus.main as m
    # Redirect onboarding state file to tmp_path for isolation
    m._ONBOARDING_FILE = tmp_path / "onboarding.json"
    return TestClient(m.app)


def test_onboarding_state_endpoint_returns_all_platforms(onboarding_client):
    r = onboarding_client.get("/api/onboarding/state")
    assert r.status_code == 200
    data = r.json()
    for p in ["gemini", "chatgpt", "claude", "perplexity", "grok", "copilot", "deepseek", "mistral"]:
        assert p in data


def test_onboarding_skip_marks_platform_skipped(onboarding_client, tmp_path):
    import chorus.main as m
    m._ONBOARDING_FILE = tmp_path / "onboarding.json"
    r = onboarding_client.post("/api/onboarding/chatgpt/skip")
    assert r.status_code == 200
    from chorus.onboarding import load_state
    state = load_state(tmp_path / "onboarding.json")
    assert state["chatgpt"]["status"] == "skipped"


def test_onboarding_unknown_platform_returns_400(onboarding_client):
    r = onboarding_client.post("/api/onboarding/fakePlatform/skip")
    assert r.status_code == 400


def test_onboarding_status_no_context_returns_not_authenticated(onboarding_client):
    """Without an open browser context, status should return authenticated=False."""
    r = onboarding_client.get("/api/onboarding/gemini/status")
    assert r.status_code == 200
    data = r.json()
    assert "authenticated" in data
    assert data["authenticated"] is False
