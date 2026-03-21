import asyncio
from .base import BaseAI


class Mistral(BaseAI):
    name         = "Mistral"
    url          = "https://chat.mistral.ai"
    color        = "#ff7000"
    icon         = "🔶"
    platform_key = "mistral"

    async def submit_prompt(self, prompt: str) -> None:
        await self.page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        await self.assert_authenticated()

        try:
            input_sel = (
                'textarea[placeholder*="Ask"], '
                'textarea[placeholder*="Message"], '
                'textarea'
            )
            el = await self.page.wait_for_selector(input_sel, timeout=10000)
            await el.click()
            await el.fill(prompt)
            await asyncio.sleep(0.5)

            try:
                send_btn = await self.page.wait_for_selector(
                    'button[aria-label*="Send"], '
                    'button[type="submit"]:not([disabled])',
                    timeout=3000
                )
                await send_btn.click()
            except Exception:
                await self.page.keyboard.press("Enter")
        except Exception as e:
            raise RuntimeError(f"Mistral: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()
        stable_needed = 3.5

        while asyncio.get_running_loop().time() < deadline:
            try:
                # Scope to LAST assistant message only — no page-wide fallback
                current = await self._collect_last_in(
                    '[data-role="assistant"], [class*="assistant-message"]',
                    'p'
                )
                if current and len(current) < 80:
                    current = ""  # too short to be a real response
                if current != last_text:
                    last_text = current
                    stable_since = asyncio.get_running_loop().time()
                elif current and (asyncio.get_running_loop().time() - stable_since) > stable_needed:
                    return self._clean_response(current)
            except Exception:
                pass
            await asyncio.sleep(0.8)

        if not last_text:
            last_text = await self._js_extract()
        return self._clean_response(last_text) or "[No response captured]"
