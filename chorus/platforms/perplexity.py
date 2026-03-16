import asyncio
from urllib.parse import quote
from .base import BaseAI


class Perplexity(BaseAI):
    name         = "Perplexity"
    url          = "https://perplexity.ai"
    color        = "#20b8cd"
    icon         = "🔭"
    platform_key = "perplexity"

    async def submit_prompt(self, prompt: str) -> None:
        encoded = quote(prompt)
        await self.page.goto(f"{self.url}/?q={encoded}", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        await self.assert_authenticated()

        # Check if already submitted via URL param
        try:
            await self.page.wait_for_selector(self._response_sel(), timeout=5000)
            return
        except Exception:
            pass

        try:
            el = await self.page.wait_for_selector(self._input_sel(), timeout=10000)
            await el.click()
            await el.fill(prompt)
            await asyncio.sleep(0.5)

            send_sel = self._send_sel()
            if send_sel:
                try:
                    btn = await self.page.wait_for_selector(send_sel, timeout=3000)
                    await btn.click()
                    return
                except Exception:
                    pass
            await self.page.keyboard.press("Enter")
        except Exception as e:
            raise RuntimeError(f"Perplexity: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_event_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_event_loop().time()
        stable_needed = 3.5

        while asyncio.get_event_loop().time() < deadline:
            try:
                current = await self._collect_blocks()
                if current != last_text:
                    last_text = current
                    stable_since = asyncio.get_event_loop().time()
                elif current and (asyncio.get_event_loop().time() - stable_since) > stable_needed:
                    return current
            except Exception:
                pass
            await asyncio.sleep(0.8)

        return last_text or "[No response captured]"
