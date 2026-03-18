"""
Tests for the FastAPI HTTP endpoints in main.py.

The browser manager's start/stop are patched to prevent real browser
launches. Individual tests pre-populate active_sessions / prompt_history
directly to test endpoint logic in isolation.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _clear_state():
    """Reset shared in-memory state before each test."""
    import chorus.main as m
    m.active_sessions.clear()
    m.prompt_history.clear()
    yield
    m.active_sessions.clear()
    m.prompt_history.clear()


@pytest.fixture
def client(tmp_path):
    import chorus.main as m
    m._ONBOARDING_FILE = tmp_path / "onboarding.json"
    with patch.object(m.browser_manager, "start", new_callable=AsyncMock), \
         patch.object(m.browser_manager, "stop", new_callable=AsyncMock):
        yield TestClient(m.app)


# ── /api/platforms ────────────────────────────────────────────────────────────

def test_list_platforms_returns_all_eight(client):
    r = client.get("/api/platforms")
    assert r.status_code == 200
    data = r.json()
    expected = {"gemini", "chatgpt", "claude", "perplexity", "grok", "copilot", "deepseek", "mistral"}
    assert set(data.keys()) == expected


def test_list_platforms_each_has_name_color_icon(client):
    r = client.get("/api/platforms")
    for meta in r.json().values():
        assert "name" in meta
        assert "color" in meta
        assert "icon" in meta


# ── /api/query ────────────────────────────────────────────────────────────────

def test_query_empty_prompt_returns_400(client):
    r = client.post("/api/query", json={"prompt": "   ", "platforms": ["gemini"]})
    assert r.status_code == 400


def test_query_blank_prompt_returns_400(client):
    r = client.post("/api/query", json={"prompt": "", "platforms": ["gemini"]})
    assert r.status_code == 400


def test_query_no_valid_platforms_returns_400(client):
    r = client.post("/api/query", json={"prompt": "hello", "platforms": ["notreal", "alsonotreal"]})
    assert r.status_code == 400


def test_query_valid_request_returns_session_id(client):
    with patch("chorus.main.asyncio.create_task"):
        r = client.post("/api/query", json={"prompt": "hello", "platforms": ["gemini"]})
    assert r.status_code == 200
    assert "session_id" in r.json()


def test_query_creates_session_in_active_sessions(client):
    import chorus.main as m
    with patch("chorus.main.asyncio.create_task"):
        r = client.post("/api/query", json={"prompt": "test prompt", "platforms": ["gemini", "chatgpt"]})
    sid = r.json()["session_id"]
    assert sid in m.active_sessions
    assert m.active_sessions[sid]["prompt"] == "test prompt"


# ── /api/sessions/{id} ────────────────────────────────────────────────────────

def test_get_session_404_for_unknown(client):
    r = client.get("/api/sessions/doesnotexist")
    assert r.status_code == 404


def test_get_session_returns_session_data(client):
    import chorus.main as m
    m.active_sessions["abc123"] = {
        "prompt": "hello", "platforms": ["gemini"],
        "responses": {"gemini": "Four."}, "status": "complete",
    }
    r = client.get("/api/sessions/abc123")
    assert r.status_code == 200
    assert r.json()["prompt"] == "hello"
    assert r.json()["status"] == "complete"


# ── /api/history ──────────────────────────────────────────────────────────────

def _make_entry(sid, prompt="test"):
    return {
        "id": sid, "prompt": prompt, "platforms": ["gemini"],
        "responses": {"gemini": "Four."},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def test_history_empty(client):
    r = client.get("/api/history")
    assert r.status_code == 200
    assert r.json() == []


def test_history_returns_most_recent_first(client):
    import chorus.main as m
    m.prompt_history.extend([_make_entry("first"), _make_entry("second"), _make_entry("third")])
    r = client.get("/api/history")
    ids = [e["id"] for e in r.json()]
    assert ids == ["third", "second", "first"]


def test_history_limit_param(client):
    import chorus.main as m
    for i in range(10):
        m.prompt_history.append(_make_entry(f"s{i}"))
    r = client.get("/api/history?limit=3")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_delete_history_item(client):
    import chorus.main as m
    m.prompt_history.append(_make_entry("todelete"))
    m.prompt_history.append(_make_entry("tokeep"))
    with patch("chorus.main.save_history"):
        r = client.delete("/api/history/todelete")
    assert r.status_code == 200
    assert all(e["id"] != "todelete" for e in m.prompt_history)
    assert any(e["id"] == "tokeep" for e in m.prompt_history)


# ── /api/export ───────────────────────────────────────────────────────────────

def test_export_404_for_unknown_session(client):
    r = client.get("/api/export/nosuchid")
    assert r.status_code == 404


def test_export_renders_string_responses(client):
    import chorus.main as m
    m.prompt_history.append({
        "id": "exp1", "prompt": "What is 2+2?", "platforms": ["gemini"],
        "responses": {"gemini": "Four."},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    r = client.get("/api/export/exp1")
    assert r.status_code == 200
    assert "Four." in r.text
    assert "What is 2+2?" in r.text


def test_export_renders_dict_error_responses_without_crash(client):
    """Regression: export used to 500 when responses contained error dicts."""
    import chorus.main as m
    m.prompt_history.append({
        "id": "exp2", "prompt": "hello", "platforms": ["gemini", "chatgpt"],
        "responses": {
            "gemini": "Four.",
            "chatgpt": {"error": True, "error_code": "auth_expired", "message": "Session expired."},
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    r = client.get("/api/export/exp2")
    assert r.status_code == 200
    assert "Four." in r.text
    assert "Session expired." in r.text


def test_export_labels_error_responses_as_italic(client):
    import chorus.main as m
    m.prompt_history.append({
        "id": "exp3", "prompt": "hi", "platforms": ["chatgpt"],
        "responses": {"chatgpt": {"error": True, "error_code": "rate_limited", "message": "Too many requests."}},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    r = client.get("/api/export/exp3")
    assert "_Error:" in r.text


# ── /api/sessions/{id}/consensus ──────────────────────────────────────────────

def test_consensus_404_for_unknown_session(client):
    r = client.get("/api/sessions/nosuchid/consensus")
    assert r.status_code == 404


def test_consensus_422_when_no_valid_string_responses(client):
    """Regression: used to crash when all responses were error dicts."""
    import chorus.main as m
    m.active_sessions["cs1"] = {
        "prompt": "hi", "platforms": ["gemini"], "status": "complete",
        "responses": {"gemini": {"error": True, "error_code": "auth_expired", "message": "expired"}},
    }
    r = client.get("/api/sessions/cs1/consensus")
    assert r.status_code == 422


def test_consensus_200_filters_out_error_dicts(client):
    """Regression: consensus should silently skip dict error responses."""
    import chorus.main as m
    m.active_sessions["cs2"] = {
        "prompt": "hi", "platforms": ["gemini", "chatgpt"], "status": "complete",
        "responses": {
            "gemini": "Machine learning is a subset of artificial intelligence systems.",
            "chatgpt": {"error": True, "error_code": "auth_expired", "message": "expired"},
        },
    }
    # One valid string response is not enough for meaningful consensus,
    # but it should not crash — it'll return 422 (no valid responses after filter)
    # Actually with one valid response _build_consensus works fine
    m.prompt_history.append({
        "id": "cs2", "prompt": "hi", "platforms": ["gemini", "chatgpt"],
        "responses": {
            "gemini": "Machine learning is a subset of artificial intelligence systems.",
            "chatgpt": {"error": True, "error_code": "auth_expired", "message": "expired"},
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    r = client.get("/api/sessions/cs2/consensus")
    assert r.status_code == 200
    data = r.json()
    assert "platform_count" in data
    assert data["platform_count"] == 1  # only gemini had a valid response


# ── /api/sessions/{id}/followup ───────────────────────────────────────────────

def test_followup_404_for_unknown_session(client):
    r = client.post("/api/sessions/nosuchid/followup", json={"prompt": "hi"})
    assert r.status_code == 404


def test_followup_400_for_empty_prompt(client):
    import chorus.main as m
    m.active_sessions["fu1"] = {
        "prompt": "orig", "platforms": ["gemini"],
        "responses": {"gemini": "Four."}, "status": "complete",
    }
    r = client.post("/api/sessions/fu1/followup", json={"prompt": "  "})
    assert r.status_code == 400


def test_followup_409_when_session_still_running(client):
    import chorus.main as m
    m.active_sessions["fu2"] = {
        "prompt": "orig", "platforms": ["gemini"],
        "responses": {}, "status": "running",
    }
    r = client.post("/api/sessions/fu2/followup", json={"prompt": "and then?"})
    assert r.status_code == 409


def test_followup_returns_new_session_id(client):
    import chorus.main as m
    m.active_sessions["fu3"] = {
        "prompt": "orig", "platforms": ["gemini"],
        "responses": {"gemini": "Four."}, "status": "complete",
    }
    with patch("chorus.main.asyncio.create_task"):
        r = client.post("/api/sessions/fu3/followup", json={"prompt": "why?"})
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert data["parent_id"] == "fu3"
    assert data["session_id"] != "fu3"


# ── Retry max-retries ─────────────────────────────────────────────────────────

def test_retry_max_retries_returns_422(client):
    import chorus.main as m
    m.active_sessions["rt1"] = {
        "prompt": "hello", "platforms": ["gemini"],
        "responses": {"gemini": {"error": True, "error_code": "timeout", "message": "timed out"}},
        "status": "complete",
        "_retry_counts": {"gemini": 3},  # already at max
    }
    r = client.post("/api/sessions/rt1/retry/gemini")
    assert r.status_code == 422


def test_retry_unknown_platform_returns_400(client):
    import chorus.main as m
    m.active_sessions["rt2"] = {
        "prompt": "hello", "platforms": ["gemini"],
        "responses": {}, "status": "complete",
    }
    r = client.post("/api/sessions/rt2/retry/notaplatform")
    assert r.status_code == 400
