import asyncio
from urllib.parse import quote
from .base import BaseAI


class Perplexity(BaseAI):
    name  = "Perplexity"
    url   = "https://perplexity.ai"
    color = "#20b8cd"
    icon  = "🔭"

    async def submit_prompt(self, prompt: str) -> None:
        encoded = quote(prompt)
        await self.page.goto(f"{self.url}/?q={encoded}", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Check if already submitted
        try:
            await self.page.wait_for_selector(
                '.prose, [class*="answer"], [class*="response"]',
                timeout=5000
            )
            return
        except Exception:
            pass

        # Manual submit
        try:
            input_sel = 'textarea[placeholder*="Ask"], textarea[name="q"], textarea'
            el = await self.page.wait_for_selector(input_sel, timeout=10000)
            await el.click()
            await el.fill(prompt)
            await asyncio.sleep(0.5)

            try:
                send_btn = await self.page.wait_for_selector(
                    'button[aria-label*="Submit"], button[type="submit"]',
                    timeout=3000
                )
                await send_btn.click()
            except Exception:
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
                blocks = await self.page.query_selector_all(
                    '.prose p, [class*="answer"] p, [class*="prose"] p, '
                    '[data-testid*="answer"] p'
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
