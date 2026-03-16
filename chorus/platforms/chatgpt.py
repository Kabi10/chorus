import asyncio
from urllib.parse import quote
from .base import BaseAI


class ChatGPT(BaseAI):
    name  = "ChatGPT"
    url   = "https://chatgpt.com"
    color = "#10a37f"
    icon  = "🟢"

    async def submit_prompt(self, prompt: str) -> None:
        encoded = quote(prompt)
        await self.page.goto(f"{self.url}/?q={encoded}", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Check if already submitted via URL param
        try:
            await self.page.wait_for_selector(
                '[data-message-author-role="assistant"]',
                timeout=5000
            )
            return  # Already submitted
        except Exception:
            pass

        # Manual submit
        try:
            input_sel = "#prompt-textarea, textarea[placeholder], div[contenteditable='true']"
            el = await self.page.wait_for_selector(input_sel, timeout=10000)
            await el.click()
            await self.page.keyboard.type(prompt, delay=15)
            await asyncio.sleep(0.5)

            # Try send button first, fallback to Enter
            try:
                send_btn = await self.page.wait_for_selector(
                    '[data-testid="send-button"]:not([disabled]), button[aria-label="Send message"]',
                    timeout=3000
                )
                await send_btn.click()
            except Exception:
                await self.page.keyboard.press("Enter")
        except Exception as e:
            raise RuntimeError(f"ChatGPT: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(2)
        deadline = asyncio.get_event_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_event_loop().time()
        stable_needed = 3.5

        while asyncio.get_event_loop().time() < deadline:
            try:
                # Wait for send button to re-enable (generation complete)
                disabled = await self.page.query_selector('[data-testid="send-button"][disabled]')
                generating = disabled is not None

                blocks = await self.page.query_selector_all(
                    '[data-message-author-role="assistant"] .markdown, '
                    '[data-message-author-role="assistant"] p'
                )
                if blocks:
                    texts = [await b.text_content() or "" for b in blocks]
                    current = "\n".join(t.strip() for t in texts if t.strip())
                    if current != last_text:
                        last_text = current
                        stable_since = asyncio.get_event_loop().time()
                    elif current and not generating and (asyncio.get_event_loop().time() - stable_since) > stable_needed:
                        return current
            except Exception:
                pass
            await asyncio.sleep(0.8)

        return last_text or "[No response captured]"
