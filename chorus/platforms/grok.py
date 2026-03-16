import asyncio
from .base import BaseAI


class Grok(BaseAI):
    name         = "Grok"
    url          = "https://x.com/i/grok"
    color        = "#1d9bf0"
    icon         = "✕"
    platform_key = "grok"

    async def submit_prompt(self, prompt: str) -> None:
        await self.page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Check if we land on a ready state
        try:
            await self.page.wait_for_selector(
                'textarea, [contenteditable="true"]',
                timeout=10000
            )
        except Exception as e:
            raise RuntimeError(f"Grok: input not found — {e}")

        try:
            input_sel = 'textarea[placeholder], textarea'
            el = await self.page.wait_for_selector(input_sel, timeout=8000)
            await el.click()
            await el.fill(prompt)
            await asyncio.sleep(0.5)

            try:
                send_btn = await self.page.wait_for_selector(
                    'button[aria-label*="Send"], button[data-testid*="send"], '
                    'button[type="submit"]:not([disabled])',
                    timeout=3000
                )
                await send_btn.click()
            except Exception:
                await self.page.keyboard.press("Enter")
        except Exception as e:
            raise RuntimeError(f"Grok: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_event_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_event_loop().time()
        stable_needed = 3.0

        while asyncio.get_event_loop().time() < deadline:
            try:
                # Grok uses data-testid="bot-message" or role="assistant"
                blocks = await self.page.query_selector_all(
                    '[data-testid="bot-message"] p, '
                    '[data-testid="bot-message"], '
                    '.prose p, .r-1adg3ll p'
                )
                if blocks:
                    texts = [await b.text_content() or "" for b in blocks]
                    current = "\n".join(t.strip() for t in texts if t.strip())
                    if current != last_text:
                        last_text = current
                        stable_since = asyncio.get_event_loop().time()
                    elif current and (asyncio.get_event_loop().time() - stable_since) > stable_needed:
                        return current
            except Exception:
                pass
            await asyncio.sleep(0.8)

        return last_text or "[No response captured]"
