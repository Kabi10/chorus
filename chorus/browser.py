"""
Playwright browser session manager.
All platforms share one persistent Chrome profile at ~/.chorus/profile/
so sessions stay fresh while the browser is running — no per-platform login needed.
"""
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext, Page

PROFILE_DIR = Path.home() / ".chorus" / "profile"


class BrowserManager:
    def __init__(self):
        self._playwright = None
        self._ctx: BrowserContext | None = None
        self._pages: dict[str, Page] = {}

    @property
    def playwright(self):
        return self._playwright

    async def start(self):
        self._playwright = await async_playwright().start()
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
