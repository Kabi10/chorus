"""
Playwright browser session manager.
Each platform gets its own persistent profile directory so login is saved.
"""
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

PROFILES_DIR = Path.home() / ".chorus" / "profiles"


class BrowserManager:
    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._contexts: dict[str, BrowserContext] = {}

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

    async def stop(self):
        for ctx in self._contexts.values():
            await ctx.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def get_context(self, platform: str, profile: str = "default") -> BrowserContext:
        key = f"{platform}:{profile}"
        if key not in self._contexts:
            profile_dir = PROFILES_DIR / platform / profile
            profile_dir.mkdir(parents=True, exist_ok=True)
            ctx = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 800},
                no_viewport=False,
            )
            self._contexts[key] = ctx
        return self._contexts[key]

    async def get_page(self, platform: str, profile: str = "default") -> Page:
        ctx = await self.get_context(platform, profile)
        if ctx.pages:
            return ctx.pages[0]
        return await ctx.new_page()

    def list_profiles(self, platform: str) -> list[str]:
        d = PROFILES_DIR / platform
        if not d.exists():
            return ["default"]
        return [p.name for p in d.iterdir() if p.is_dir()] or ["default"]


# Singleton
manager = BrowserManager()
