"""Base class for all AI platform connectors."""
import asyncio
import json
from abc import ABC, abstractmethod
from pathlib import Path
from playwright.async_api import Page

SELECTORS_FILE = Path(__file__).parent.parent / "selectors.json"

def _load_selectors() -> dict:
    try:
        return json.loads(SELECTORS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

ALL_SELECTORS: dict = _load_selectors()


class BaseAI(ABC):
    name:        str = "base"
    url:         str = ""
    color:       str = "#888"
    icon:        str = "🤖"
    platform_key: str = ""   # must match selectors.json key

    def __init__(self, page: Page):
        self.page = page
        self._sel = ALL_SELECTORS.get(self.platform_key, {})

    # ── Selector helpers ──────────────────────────────────────────

    def _input_sel(self) -> str:
        return ", ".join(self._sel.get("input", ["textarea"]))

    def _send_sel(self) -> str:
        btns = self._sel.get("send_button", [])
        return ", ".join(btns) if btns else ""

    def _response_sel(self) -> str:
        return ", ".join(self._sel.get("response", [".prose p"]))

    def _auth_sel(self) -> str:
        return ", ".join(self._sel.get("auth_check", []))

    def _loading_sel(self) -> str:
        return ", ".join(self._sel.get("loading_indicator", []))

    # ── Auth / CAPTCHA detection ──────────────────────────────────

    async def check_auth(self) -> bool:
        """Returns True if a login wall or CAPTCHA is detected."""
        url = self.page.url
        if any(kw in url for kw in ["login", "signin", "auth", "accounts.google", "microsoft.com/login"]):
            return True
        sel = self._auth_sel()
        if sel:
            try:
                el = await self.page.query_selector(sel)
                return el is not None
            except Exception:
                pass
        return False

    async def assert_authenticated(self):
        """Raise a clear error if not logged in."""
        if await self.check_auth():
            raise RuntimeError(
                f"{self.name}: not logged in. Open Chorus, click ⚙ on {self.name}, "
                f"add an account, and log in once. Current URL: {self.page.url}"
            )

    async def is_authenticated(self) -> bool:
        """Returns True if the user is logged in (inverse of check_auth)."""
        return not await self.check_auth()

    # ── Abstract interface ────────────────────────────────────────

    @abstractmethod
    async def submit_prompt(self, prompt: str) -> None:
        """Navigate to the AI, find the input, type and submit the prompt."""

    @abstractmethod
    async def wait_for_response(self, timeout: int = 90) -> str:
        """Wait until the AI finishes generating and return the full response text."""

    async def run(self, prompt: str, timeout: int = 90) -> str:
        """Full flow: submit + wait. Returns response text."""
        await self.submit_prompt(prompt)
        return await self.wait_for_response(timeout)

    # ── Convenience helpers ───────────────────────────────────────

    async def _type_into(self, selector: str, text: str, use_fill: bool = False):
        el = await self.page.wait_for_selector(selector, timeout=15000)
        await el.click()
        if use_fill:
            await el.fill(text)
        else:
            await self.page.keyboard.type(text, delay=20)

    async def _wait_stable(self, selector: str, stable_ms: int = 2500, timeout: int = 90) -> str:
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()

        while asyncio.get_running_loop().time() < deadline:
            try:
                el = await self.page.query_selector(selector)
                if el:
                    current = (await el.text_content() or "").strip()
                    if current != last_text:
                        last_text = current
                        stable_since = asyncio.get_running_loop().time()
                    elif current and (asyncio.get_running_loop().time() - stable_since) > (stable_ms / 1000):
                        return current
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return last_text

    async def _collect_blocks(self) -> str:
        """Collect text from all response paragraph blocks using selectors.json."""
        sel = self._response_sel()
        blocks = await self.page.query_selector_all(sel)
        if not blocks:
            return ""
        texts = [await b.text_content() or "" for b in blocks]
        return "\n".join(t.strip() for t in texts if t.strip())
