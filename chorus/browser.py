"""
Playwright browser session manager.

Priority order:
  1. CDP (remote debugging) — attaches to your already-running Chrome on port 9222.
     Launch Chrome with: chrome.exe --remote-debugging-port=9222
     Sessions are your real Chrome sessions — zero re-login needed.

  2. Persistent profile at ~/.chorus/profile/ — a dedicated Chrome window with
     saved sessions.  Log in once; sessions persist across Chorus restarts.
"""
import asyncio
import aiohttp
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext, Page

PROFILE_DIR = Path.home() / ".chorus" / "profile"
CDP_URL = "http://localhost:9222"


async def _cdp_available() -> bool:
    """Return True if Chrome remote debugging is reachable on port 9222."""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{CDP_URL}/json/version", timeout=aiohttp.ClientTimeout(total=1.5)) as r:
                return r.status == 200
    except Exception:
        return False


class BrowserManager:
    def __init__(self):
        self._playwright = None
        self._ctx: BrowserContext | None = None
        self._browser = None        # only set when using CDP
        self._pages: dict[str, Page] = {}
        self._using_cdp = False

    @property
    def playwright(self):
        return self._playwright

    async def start(self):
        self._playwright = await async_playwright().start()

        # ── 1. Try CDP (existing Chrome with --remote-debugging-port=9222) ──
        if await _cdp_available():
            try:
                self._browser = await self._playwright.chromium.connect_over_cdp(CDP_URL)
                # Use the first existing context (has the user's real sessions)
                contexts = self._browser.contexts
                self._ctx = contexts[0] if contexts else await self._browser.new_context()
                self._using_cdp = True
                print("[Chorus] Connected to existing Chrome via CDP — using your real sessions.")
                return
            except Exception as e:
                print(f"[Chorus] CDP available but connect failed ({e}), falling back to profile.")

        # ── 2. Persistent shared profile ──────────────────────────────────
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        launch_args = dict(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 800},
        )
        try:
            # Prefer system Chrome — sessions persist and refresh like a real browser
            self._ctx = await self._playwright.chromium.launch_persistent_context(
                channel="chrome", **launch_args
            )
        except Exception:
            # Fall back to bundled Chromium if Chrome isn't installed
            self._ctx = await self._playwright.chromium.launch_persistent_context(
                **launch_args
            )

    async def stop(self):
        if self._using_cdp:
            # Disconnect without closing the user's real Chrome process
            if self._browser:
                await self._browser.disconnect()
        else:
            if self._ctx:
                await self._ctx.close()
        if self._playwright:
            await self._playwright.stop()

    async def get_context(self, platform: str = "default", profile: str = "default") -> BrowserContext:
        """All platforms share one context (one Chrome profile)."""
        return self._ctx

    async def get_page(self, platform: str, profile: str = "default") -> Page:
        key = f"{platform}:{profile}"
        page = self._pages.get(key)
        if page is None or page.is_closed():
            page = await self._ctx.new_page()
            self._pages[key] = page
        return page

    def list_profiles(self, platform: str) -> list[str]:
        return ["default"]


# Singleton
manager = BrowserManager()
