import json
import importlib.resources


def _load_selectors():
    text = importlib.resources.files("chorus").joinpath("selectors.json").read_text()
    return json.loads(text)


ALL_PLATFORMS = ["gemini","chatgpt","claude","perplexity","grok","copilot","deepseek","mistral"]


def test_all_platforms_have_timeout_seconds():
    sel = _load_selectors()
    for p in ALL_PLATFORMS:
        assert p in sel, f"platform {p} missing from selectors.json"
        assert "timeout_seconds" in sel[p], f"{p} missing timeout_seconds"
        assert isinstance(sel[p]["timeout_seconds"], int)


def test_all_platforms_have_rate_limit_signals():
    sel = _load_selectors()
    for p in ALL_PLATFORMS:
        assert "rate_limit_signals" in sel[p], f"{p} missing rate_limit_signals"
        assert isinstance(sel[p]["rate_limit_signals"], list)


import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio


def _make_client():
    import chorus.main as m
    from fastapi.testclient import TestClient
    return TestClient(m.app)


def test_classify_error_timeout():
    from chorus.main import _classify_error
    err = asyncio.TimeoutError()
    code, msg = _classify_error("gemini", err, page_text="")
    assert code == "timeout"


def test_classify_error_rate_limited():
    from chorus.main import _classify_error
    err = Exception("some error")
    code, msg = _classify_error("gemini", err, page_text="You've reached your limit today")
    assert code == "rate_limited"


def test_classify_error_selector_error():
    from chorus.main import _classify_error
    from playwright.async_api import TimeoutError as PlaywrightTimeout
    err = PlaywrightTimeout("waiting for selector failed")
    code, msg = _classify_error("gemini", err, page_text="normal page content")
    assert code == "selector_error"


def test_retry_endpoint_404_for_unknown_session():
    c = _make_client()
    r = c.post("/api/sessions/nosuchid/retry/gemini")
    assert r.status_code == 404


def test_retry_endpoint_409_on_concurrent_retry():
    import chorus.main as m
    # Simulate a retry already in progress
    m.active_sessions["sess1"] = {
        "prompt": "test", "platforms": ["gemini"],
        "responses": {}, "status": "complete",
        "_retrying": {"gemini"},
    }
    c = _make_client()
    r = c.post("/api/sessions/sess1/retry/gemini")
    assert r.status_code == 409
    del m.active_sessions["sess1"]


# ── Regression: _classify_error — browser_closed ─────────────────────────────

def test_classify_error_browser_closed():
    from chorus.main import _classify_error
    err = Exception("Target page, context or browser has been closed")
    code, msg = _classify_error("gemini", err, page_text="")
    assert code == "browser_closed"
    assert "browser" in msg.lower()


def test_classify_error_browser_closed_message_is_human_readable():
    from chorus.main import _classify_error
    err = Exception("Target page, context or browser has been closed")
    _, msg = _classify_error("chatgpt", err, page_text="")
    # Must not contain raw Playwright exception text
    assert "Target page" not in msg


# ── Regression: selectors.json CSS validity ───────────────────────────────────

def test_no_wildcard_in_attribute_selectors():
    """[attr='value*'] is invalid CSS — only [attr^=], [$=], [*=] are valid."""
    sel = _load_selectors()
    import re
    for platform, config in sel.items():
        for key, selectors in config.items():
            if not isinstance(selectors, list):
                continue
            for s in selectors:
                # Flag selectors like [attr='val*ue'] — literal * inside quoted value
                bad = re.findall(r"\[[\w-]+='.+\*[^=]", s)
                assert not bad, (
                    f"{platform}.{key}: invalid wildcard in attribute selector: {s!r}"
                )


# ── Regression: check_auth covers new URL keyword additions ──────────────────

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("keyword", ["sign-in", "sign_in", "signup", "register"])
async def test_check_auth_new_keywords(keyword):
    """Keywords added after initial auth detection — must be in _AUTH_URL_KEYWORDS."""
    from chorus.platforms.base import BaseAI, _AUTH_URL_KEYWORDS
    assert keyword in _AUTH_URL_KEYWORDS, (
        f"'{keyword}' not in _AUTH_URL_KEYWORDS — auth detection will miss this pattern"
    )
