import asyncio
from .base import BaseAI


class ChatGPT(BaseAI):
    name         = "ChatGPT"
    url          = "https://chatgpt.com"
    color        = "#10a37f"
    icon         = "🟢"
    platform_key = "chatgpt"

    async def submit_prompt(self, prompt: str) -> None:
        await self.page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(8)  # ChatGPT React app needs time to fully render
        await self.assert_authenticated()

        try:
            # Extended selector list covering multiple ChatGPT UI generations
            input_sel = (
                "#prompt-textarea, "
                "div[contenteditable='true'][aria-label*='Message'], "
                "div[contenteditable='true'][aria-label*='message'], "
                "div[contenteditable='true'][role='textbox'], "
                "textarea[placeholder*='Message'], "
                "div[contenteditable='true'][data-slate-editor], "
                "div[contenteditable='true']"
            )
            el = await self.page.wait_for_selector(input_sel, timeout=25000)
            try:
                await el.click()
            except Exception:
                await self._js_click(el)
            tag = await el.evaluate("el => el.tagName.toLowerCase()")
            if tag == "textarea":
                await el.fill(prompt)
            else:
                await self.page.keyboard.type(prompt, delay=10)
            await asyncio.sleep(0.8)

            # Try send button, fall back to Enter
            try:
                btn = await self.page.wait_for_selector(
                    "button[data-testid='send-button']:not([disabled]), "
                    "button[aria-label='Send message']:not([disabled])",
                    timeout=4000
                )
                try:
                    await btn.click()
                except Exception:
                    await self._js_click(btn)
                return
            except Exception:
                pass
            await self.page.keyboard.press("Enter")
        except Exception as e:
            raise RuntimeError(f"ChatGPT: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()
        stable_needed = 3.0

        while asyncio.get_running_loop().time() < deadline:
            try:
                loading = await self.page.query_selector(self._loading_sel()) if self._loading_sel() else None
                # Scope to LAST assistant message only — prevents multi-turn repetition
                current = await self._collect_last_in(
                    '[data-message-author-role="assistant"]',
                    '.markdown p, p'
                ) or await self._collect_blocks()
                if current != last_text:
                    last_text = current
                    stable_since = asyncio.get_running_loop().time()
                elif current and not loading and (asyncio.get_running_loop().time() - stable_since) > stable_needed:
                    return self._clean_response(current)
            except Exception:
                pass
            await asyncio.sleep(0.8)

        if not last_text:
            last_text = await self._js_extract()
        return self._clean_response(last_text) or "[No response captured]"
