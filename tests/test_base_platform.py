"""Tests for chorus/platforms/base.py — BaseAI shared logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_platform(url="https://fake.ai/chat", auth_sel=""):
    """Return a concrete BaseAI subclass with a mocked page."""
    from chorus.platforms.base import BaseAI

    class FakePlatform(BaseAI):
        name = "fake"
        url = "https://fake.ai"
        platform_key = "fake"

        async def submit_prompt(self, prompt): pass
        async def wait_for_response(self, timeout=90): return ""

    mock_page = MagicMock()
    mock_page.url = url
    mock_page.query_selector = AsyncMock(return_value=None)
    mock_page.query_selector_all = AsyncMock(return_value=[])

    ai = FakePlatform(mock_page)
    # Override auth sel if provided
    if auth_sel:
        ai._sel = {"auth_check": [auth_sel]}
    return ai, mock_page


# ── check_auth — URL keyword detection ───────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "https://fake.ai/login",
    "https://fake.ai/signin",
    "https://fake.ai/sign-in",
    "https://fake.ai/sign_in",
    "https://fake.ai/auth/callback",
    "https://fake.ai/signup",
    "https://fake.ai/register",
    "https://accounts.google.com/ServiceLogin",
    "https://login.microsoftonline.com/microsoft.com/login",
])
async def test_check_auth_detects_auth_urls(url):
    ai, _ = _make_platform(url=url)
    assert await ai.check_auth() is True


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "https://fake.ai/chat",
    "https://fake.ai/",
    "https://fake.ai/new",
    "https://chatgpt.com/",
    "https://gemini.google.com/app",
])
async def test_check_auth_does_not_flag_normal_urls(url):
    ai, _ = _make_platform(url=url)
    assert await ai.check_auth() is False


# ── check_auth — CSS selector detection ──────────────────────────────────────

@pytest.mark.asyncio
async def test_check_auth_detects_login_element_on_page():
    ai, mock_page = _make_platform(url="https://fake.ai/chat")
    # Simulate a login input element present on the page
    mock_page.query_selector = AsyncMock(return_value=MagicMock())
    ai._sel = {"auth_check": ["input[type='email']"]}
    assert await ai.check_auth() is True


@pytest.mark.asyncio
async def test_check_auth_returns_false_when_selector_finds_nothing():
    ai, mock_page = _make_platform(url="https://fake.ai/chat")
    mock_page.query_selector = AsyncMock(return_value=None)
    ai._sel = {"auth_check": ["input[type='email']"]}
    assert await ai.check_auth() is False


@pytest.mark.asyncio
async def test_check_auth_handles_selector_exception_gracefully():
    ai, mock_page = _make_platform(url="https://fake.ai/chat")
    mock_page.query_selector = AsyncMock(side_effect=Exception("page crashed"))
    ai._sel = {"auth_check": ["input[name='email']"]}
    # Should not raise — falls back to False
    assert await ai.check_auth() is False


# ── assert_authenticated ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_assert_authenticated_raises_when_on_login_page():
    ai, _ = _make_platform(url="https://fake.ai/login")
    with pytest.raises(RuntimeError, match="not logged in"):
        await ai.assert_authenticated()


@pytest.mark.asyncio
async def test_assert_authenticated_does_not_raise_when_logged_in():
    ai, _ = _make_platform(url="https://fake.ai/chat")
    await ai.assert_authenticated()  # should not raise


@pytest.mark.asyncio
async def test_assert_authenticated_error_message_includes_platform_name():
    ai, _ = _make_platform(url="https://fake.ai/login")
    with pytest.raises(RuntimeError) as exc:
        await ai.assert_authenticated()
    assert "fake" in str(exc.value).lower()


# ── is_authenticated ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_is_authenticated_is_inverse_of_check_auth_logged_in():
    ai, _ = _make_platform(url="https://fake.ai/chat")
    assert await ai.is_authenticated() is True


@pytest.mark.asyncio
async def test_is_authenticated_is_inverse_of_check_auth_logged_out():
    ai, _ = _make_platform(url="https://fake.ai/login")
    assert await ai.is_authenticated() is False


# ── _collect_blocks ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_blocks_returns_empty_when_no_elements():
    ai, mock_page = _make_platform()
    mock_page.query_selector_all = AsyncMock(return_value=[])
    result = await ai._collect_blocks()
    assert result == ""


@pytest.mark.asyncio
async def test_collect_blocks_joins_text_content():
    ai, mock_page = _make_platform()
    ai._sel = {"response": [".prose p"]}

    def make_el(text):
        el = MagicMock()
        el.text_content = AsyncMock(return_value=text)
        return el

    mock_page.query_selector_all = AsyncMock(return_value=[
        make_el("First paragraph."),
        make_el("  Second paragraph.  "),
        make_el(""),  # empty — should be filtered
    ])
    result = await ai._collect_blocks()
    assert "First paragraph." in result
    assert "Second paragraph." in result
    assert result.count("\n") == 1  # two non-empty blocks joined by one newline


# ── _js_extract ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_js_extract_returns_page_evaluate_result():
    ai, mock_page = _make_platform()
    mock_page.evaluate = AsyncMock(return_value="Some response text from the page.")
    result = await ai._js_extract()
    assert result == "Some response text from the page."


@pytest.mark.asyncio
async def test_js_extract_passes_prompt_snippet_to_js():
    ai, mock_page = _make_platform()
    mock_page.evaluate = AsyncMock(return_value="response")
    await ai._js_extract(prompt_snippet="What is")
    call_args = mock_page.evaluate.call_args
    assert "What is" in call_args[0][1]  # second positional arg is the prompt snippet


@pytest.mark.asyncio
async def test_js_extract_returns_empty_string_on_exception():
    ai, mock_page = _make_platform()
    mock_page.evaluate = AsyncMock(side_effect=Exception("JS error"))
    result = await ai._js_extract()
    assert result == ""


@pytest.mark.asyncio
async def test_js_extract_strips_whitespace():
    ai, mock_page = _make_platform()
    mock_page.evaluate = AsyncMock(return_value="  trimmed result  ")
    result = await ai._js_extract()
    assert result == "trimmed result"


@pytest.mark.asyncio
async def test_js_extract_returns_empty_when_evaluate_returns_none():
    ai, mock_page = _make_platform()
    mock_page.evaluate = AsyncMock(return_value=None)
    result = await ai._js_extract()
    assert result == ""


# ── selector helpers ──────────────────────────────────────────────────────────

def test_input_sel_falls_back_to_textarea():
    ai, _ = _make_platform()
    ai._sel = {}
    assert ai._input_sel() == "textarea"


def test_send_sel_returns_empty_when_none_configured():
    ai, _ = _make_platform()
    ai._sel = {}
    assert ai._send_sel() == ""


def test_response_sel_falls_back_to_prose_p():
    ai, _ = _make_platform()
    ai._sel = {}
    assert ai._response_sel() == ".prose p"


def test_input_sel_joins_multiple_selectors():
    ai, _ = _make_platform()
    ai._sel = {"input": ["textarea", "div[contenteditable]"]}
    assert ai._input_sel() == "textarea, div[contenteditable]"
