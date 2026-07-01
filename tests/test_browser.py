"""Tests for chorus/browser.py — BrowserManager and helpers."""
import pytest
from unittest.mock import AsyncMock, MagicMock


# ── BrowserManager.get_page ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_page_creates_new_page_on_first_call():
    from chorus.browser import BrowserManager

    bm = BrowserManager()
    mock_page = MagicMock()
    mock_page.is_closed = MagicMock(return_value=False)

    mock_ctx = MagicMock()
    mock_ctx.new_page = AsyncMock(return_value=mock_page)
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
    bm._ctx = mock_ctx
    bm._pages["gemini:default"] = closed_page

    page = await bm.get_page("gemini")

    mock_ctx.new_page.assert_called_once()
    assert page is new_page


@pytest.mark.asyncio
async def test_get_page_keys_by_platform_and_profile():
    """Different profiles for the same platform must get separate pages."""
    from chorus.browser import BrowserManager

    bm = BrowserManager()
    mock_ctx = MagicMock()
    mock_ctx.new_page = AsyncMock(side_effect=lambda: MagicMock(is_closed=MagicMock(return_value=False)))
    bm._ctx = mock_ctx

    page_default = await bm.get_page("gemini", "default")
    page_work = await bm.get_page("gemini", "work")

    assert page_default is not page_work
    assert set(bm._pages) == {"gemini:default", "gemini:work"}


# ── BrowserManager.stop ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stop_closes_context_and_playwright():
    from chorus.browser import BrowserManager

    bm = BrowserManager()
    bm._ctx = MagicMock()
    bm._ctx.close = AsyncMock()
    bm._playwright = MagicMock()
    bm._playwright.stop = AsyncMock()

    await bm.stop()

    bm._ctx.close.assert_called_once()
    bm._playwright.stop.assert_called_once()


@pytest.mark.asyncio
async def test_stop_is_safe_when_never_started():
    from chorus.browser import BrowserManager

    bm = BrowserManager()
    await bm.stop()  # must not raise
