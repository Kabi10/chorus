import asyncio
from .base import BaseAI


class DeepSeek(BaseAI):
    name         = "DeepSeek"
    url          = "https://chat.deepseek.com"
    color        = "#4d6bfe"
    icon         = "🔵"
    platform_key = "deepseek"

    async def submit_prompt(self, prompt: str) -> None:
        await self.page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        await self.assert_authenticated()

        try:
            input_sel = (
                'textarea[placeholder*="Send"], '
                'textarea[placeholder*="Ask"], '
                'textarea'
            )
            el = await self.page.wait_for_selector(input_sel, timeout=10000)
            await el.click()
            await el.fill(prompt)
            await asyncio.sleep(0.5)

            try:
                send_btn = await self.page.wait_for_selector(
                    'button[aria-label*="Send"], '
                    'div[role="button"][aria-label*="Send"], '
                    'button[type="submit"]:not([disabled])',
                    timeout=3000
                )
                await send_btn.click()
            except Exception:
                await self.page.keyboard.press("Enter")
        except Exception as e:
            raise RuntimeError(f"DeepSeek: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()
        stable_needed = 3.5

        while asyncio.get_running_loop().time() < deadline:
            try:
                # DeepSeek uses .ds-markdown or .chat-message-content
                blocks = await self.page.query_selector_all(
                    '.ds-markdown p, '
                    '.chat-message-content p, '
                    '[class*="assistant"] p, '
                    '.prose p'
                )
                if blocks:
                    texts = [await b.text_content() or "" for b in blocks]
                    current = "\n".join(t.strip() for t in texts if t.strip())
                    if current != last_text:
                        last_text = current
                        stable_since = asyncio.get_running_loop().time()
                    elif current and (asyncio.get_running_loop().time() - stable_since) > stable_needed:
                        return current
            except Exception:
                pass
            await asyncio.sleep(0.8)

        return last_text or "[No response captured]"
