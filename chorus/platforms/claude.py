import asyncio
from .base import BaseAI


class Claude(BaseAI):
    name         = "Claude"
    url          = "https://claude.ai/new"
    color        = "#d97706"
    icon         = "🟣"
    platform_key = "claude"

    async def submit_prompt(self, prompt: str) -> None:
        await self.page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        await self.assert_authenticated()

        try:
            el = await self.page.wait_for_selector(self._input_sel(), timeout=20000)
            await el.click()
            await self.page.keyboard.type(prompt, delay=15)
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
            raise RuntimeError(f"Claude: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(2)
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()
        stable_needed = 3.0

        while asyncio.get_running_loop().time() < deadline:
            try:
                streaming = await self.page.query_selector(self._loading_sel()) if self._loading_sel() else None
                # Scope to LAST assistant message only — try multiple selectors
                current = await self._collect_last_in(
                    '[data-testid="assistant-message"], '
                    '[data-author="assistant"], '
                    'div[class*="AssistantMessage"], '
                    'div[class*="assistant-message"]',
                    '.font-claude-message p, [class*="prose"] p, p'
                )
                if current and len(current) < 80:
                    current = ""  # too short to be a real response
                if current != last_text:
                    last_text = current
                    stable_since = asyncio.get_running_loop().time()
                elif current and not streaming and (asyncio.get_running_loop().time() - stable_since) > stable_needed:
                    return self._clean_response(current)
            except Exception:
                pass
            await asyncio.sleep(0.8)

        if not last_text:
            last_text = await self._js_extract()
        return self._clean_response(last_text) or "[No response captured]"
