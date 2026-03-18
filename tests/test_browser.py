"""Tests for chorus/browser.py — BrowserManager and helpers."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── _cdp_available ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cdp_available_returns_true_on_200():
    import aiohttp
    from chorus.browser import _cdp_available

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("chorus.browser.aiohttp.ClientSession", return_value=mock_session):
        result = await _cdp_available()

    assert result is True


@pytest.mark.asyncio
async def test_cdp_available_returns_false_on_non_200():
    from chorus.browser import _cdp_available

    mock_response = MagicMock()
    mock_response.status = 404
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_response)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("chorus.browser.aiohttp.ClientSession", return_value=mock_session):
        result = await _cdp_available()

    assert result is False


@pytest.mark.asyncio
async def test_cdp_available_returns_false_on_connection_error():
    from chorus.browser import _cdp_available

    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=ConnectionRefusedError)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("chorus.browser.aiohttp.ClientSession", return_value=mock_session):
        result = await _cdp_available()

    assert result is False


# ── BrowserManager.get_page ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_page_creates_new_page_on_first_call():
    from chorus.browser import BrowserManager

    bm = BrowserManager()
    mock_page = MagicMock()
    mock_page.is_closed = MagicMock(return_value=False)

    mock_ctx = MagicMock()
    mock_ctx.new_page = AsyncMock(return_value=mock_page)
    mock_ctx.pages = []  # context is alive
    bm._ctx = mock_ctx

    page = await bm.get_page("gemini")

    mock_ctx.new_page.assert_called_once()
    assert page is mock_page


@pytest.mark.asyncio
async def test_get_page_reuses_existing_open_page():
    from chorus.browser import BrowserManager

    bm = BrowserManager()
    mock_page = MagicMock()
    mock_page.is_closed = MagicMock(return_value=False)

    mock_ctx = MagicMock()
    mock_ctx.new_page = AsyncMock(return_value=mock_page)
    mock_ctx.pages = []
    bm._ctx = mock_ctx
    bm._pages["gemini:default"] = mock_page

    page = await bm.get_page("gemini")

    mock_ctx.new_page.assert_not_called()
    assert page is mock_page


@pytest.mark.asyncio
async def test_get_page_replaces_closed_page():
    from chorus.browser import BrowserManager

    bm = BrowserManager()

    closed_page = MagicMock()
    closed_page.is_closed = MagicMock(return_value=True)

    new_page = MagicMock()
    new_page.is_closed = MagicMock(return_value=False)

    mock_ctx = MagicMock()
    mock_ctx.new_page = AsyncMock(return_value=new_page)
    mock_ctx.pages = []
    bm._ctx = mock_ctx
    bm._pages["gemini:default"] = closed_page

    page = await bm.get_page("gemini")

    mock_ctx.new_page.assert_called_once()
    assert page is new_page


# ── BrowserManager._ensure_context ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_ensure_context_does_nothing_when_context_alive():
    from chorus.browser import BrowserManager

    bm = BrowserManager()
    mock_ctx = MagicMock()
    mock_ctx.pages = []  # accessing .pages works fine
    bm._ctx = mock_ctx

    bm._connect = AsyncMock()
    await bm._ensure_context()

    bm._connect.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_context_reconnects_when_context_is_none():
    from chorus.browser import BrowserManager

    bm = BrowserManager()
    bm._ctx = None
    bm._connect = AsyncMock()

    await bm._ensure_context()

    bm._connect.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_context_reconnects_when_context_raises():
    from chorus.browser import BrowserManager

    bm = BrowserManager()

    dead_ctx = MagicMock()
    type(dead_ctx).pages = property(lambda self: (_ for _ in ()).throw(Exception("closed")))
    bm._ctx = dead_ctx
    bm._connect = AsyncMock()

    await bm._ensure_context()

    bm._connect.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_context_clears_pages_on_reconnect():
    from chorus.browser import BrowserManager

    bm = BrowserManager()
    bm._ctx = None
    bm._pages["gemini:default"] = MagicMock()

    async def fake_connect():
        bm._ctx = MagicMock()
        bm._ctx.pages = []

    bm._connect = fake_connect
    await bm._ensure_context()

    assert bm._pages == {}


# ── BrowserManager.stop ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stop_disconnects_in_cdp_mode():
    from chorus.browser import BrowserManager

    bm = BrowserManager()
    bm._using_cdp = True
    bm._browser = MagicMock()
    bm._browser.disconnect = AsyncMock()
    bm._playwright = MagicMock()
    bm._playwright.stop = AsyncMock()

    await bm.stop()

    bm._browser.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_stop_closes_context_in_profile_mode():
    from chorus.browser import BrowserManager

    bm = BrowserManager()
    bm._using_cdp = False
    bm._ctx = MagicMock()
    bm._ctx.close = AsyncMock()
    bm._playwright = MagicMock()
    bm._playwright.stop = AsyncMock()

    await bm.stop()

    bm._ctx.close.assert_called_once()
