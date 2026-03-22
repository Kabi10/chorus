import asyncio
from .base import BaseAI


class HuggingChat(BaseAI):
    name         = "HuggingChat"
    url          = "https://huggingface.co/chat"
    color        = "#ff9d00"
    icon         = "🤗"
    platform_key = "huggingchat"

    async def submit_prompt(self, prompt: str) -> None:
        await self.page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        await self.assert_authenticated()

        try:
            el = await self.page.wait_for_selector(
                'textarea[placeholder="Ask anything"], textarea[placeholder*="Ask"], textarea',
                timeout=15000
            )
            # JS click bypasses actionability issues (off-screen, overlapping elements)
            await self._js_click(el)
            await asyncio.sleep(0.3)
            await el.fill(prompt)
            await asyncio.sleep(0.3)
            await self.page.keyboard.press("Enter")
        except Exception as e:
            raise RuntimeError(f"HuggingChat: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()
        stable_needed = 3.5

        while asyncio.get_running_loop().time() < deadline:
            try:
                # Wait for stop-generation button to disappear (streaming done)
                stop_btn = await self.page.query_selector(
                    'button[title="Stop generating"], button[aria-label*="Stop"]'
                )

                current = await self._collect_last_in(
                    '[data-message-role="assistant"]',
                    'div, p'
                )
                if current and len(current) < 20:
                    current = ""
                if current != last_text:
                    last_text = current
                    stable_since = asyncio.get_running_loop().time()
                elif current and not stop_btn and (
                    asyncio.get_running_loop().time() - stable_since
                ) > stable_needed:
                    return self._clean_response(current)
            except Exception:
                pass
            await asyncio.sleep(1.0)

        if not last_text:
            last_text = await self._js_extract()
        return self._clean_response(last_text) or "[No response captured]"
