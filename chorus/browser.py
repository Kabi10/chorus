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

        # Kill any orphaned Chrome process still holding the profile lock,
        # then remove stale lock files. This makes restarts always clean.
        import subprocess, sys
        profile_str = str(PROFILE_DIR)
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["powershell", "-Command",
                     f"Get-WmiObject Win32_Process -Filter 'name=\"chrome.exe\"' "
                     f"| Where-Object {{ $_.CommandLine -like '*{profile_str}*' "
                     f"  -and $_.CommandLine -notlike '*type=*' }} "
                     f"| ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"],
                    capture_output=True, timeout=5
                )
            except Exception:
                pass
        for lock_path in [
            PROFILE_DIR / "lockfile",
            PROFILE_DIR / "SingletonLock",
            PROFILE_DIR / "Default" / "LOCK",
        ]:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass

        launch_args = dict(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-position=0,0",
                "--window-size=1280,800",
            ],
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

        # Stealth: override navigator.webdriver and other automation signals
        # so sites like claude.ai don't detect Playwright
        await self._ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => false});
            // Hide Playwright/Chromium automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """)

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
