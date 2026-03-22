import asyncio
from .base import BaseAI


class MetaAI(BaseAI):
    name         = "Meta AI"
    url          = "https://www.meta.ai"
    color        = "#0082fb"
    icon         = "🔷"
    platform_key = "meta_ai"

    async def submit_prompt(self, prompt: str) -> None:
        await self.page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        await self.assert_authenticated()

        try:
            input_sel = (
                "div[contenteditable='true'][aria-label*='Message'], "
                "div[contenteditable='true'][aria-label*='Ask'], "
                "div[contenteditable='true'][aria-label*='Send'], "
                "div[contenteditable='true'][aria-label*='meta'], "
                "div[contenteditable='true'][role='textbox'], "
                "textarea[placeholder*='Ask'], "
                "textarea[placeholder*='Message'], "
                "textarea[placeholder*='meta'], "
                "input[type='text'][placeholder], "
                "textarea, "
                "div[contenteditable='true']"
            )
            el = await self.page.wait_for_selector(input_sel, timeout=30000)
            try:
                await el.click()
            except Exception:
                await self._js_click(el)
            await self.page.keyboard.type(prompt, delay=10)
            await asyncio.sleep(0.5)

            send_sel = self._send_sel()
            if send_sel:
                try:
                    btn = await self.page.wait_for_selector(send_sel, timeout=4000)
                    try:
                        await btn.click()
                    except Exception:
                        await self._js_click(btn)
                    return
                except Exception:
                    pass
            await self.page.keyboard.press("Enter")
        except Exception as e:
            raise RuntimeError(f"Meta AI: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()
        stable_needed = 3.0

        while asyncio.get_running_loop().time() < deadline:
            try:
                current = await self._collect_last_in(
                    '[data-testid="message-text"], '
                    '[class*="AssistantMessage"], '
                    '[class*="assistant-message"], '
                    '[class*="bot-message"]',
                    'p, span, div[class*="prose"] p'
                )
                if current and len(current) < 2:
                    current = ""
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
        if not last_text:
            last_text = await self._body_text_extract()
        return self._clean_response(last_text) or "[No response captured]"
