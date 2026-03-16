"""Base class for all AI platform connectors."""
import asyncio
from abc import ABC, abstractmethod
from playwright.async_api import Page


class BaseAI(ABC):
    name:     str = "base"
    url:      str = ""
    color:    str = "#888"
    icon:     str = "🤖"

    def __init__(self, page: Page):
        self.page = page

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

    async def _type_into(self, selector: str, text: str, use_fill: bool = False):
        """Type text into an element, with optional fill (faster for plain inputs)."""
        el = await self.page.wait_for_selector(selector, timeout=15000)
        await el.click()
        if use_fill:
            await el.fill(text)
        else:
            await self.page.keyboard.type(text, delay=20)

    async def _wait_stable(self, selector: str, stable_ms: int = 2500, timeout: int = 90) -> str:
        """
        Wait for an element's text to stop changing for `stable_ms` milliseconds.
        Returns the final text content.
        """
        deadline = asyncio.get_event_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() < deadline:
            try:
                el = await self.page.query_selector(selector)
                if el:
                    current = (await el.text_content() or "").strip()
                    if current != last_text:
                        last_text = current
                        stable_since = asyncio.get_event_loop().time()
                    elif current and (asyncio.get_event_loop().time() - stable_since) > (stable_ms / 1000):
                        return current
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return last_text
