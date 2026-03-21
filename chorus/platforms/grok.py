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
        await self.assert_authenticated()

        # Check if we land on a ready state (textarea OR contenteditable)
        try:
            await self.page.wait_for_selector(
                'textarea, [contenteditable="true"]',
                timeout=10000
            )
        except Exception as e:
            raise RuntimeError(f"Grok: input not found — {e}")

        try:
            # Grok uses contenteditable div in newer UI, textarea in older
            input_sel = (
                'textarea[placeholder], '
                'div[contenteditable="true"][aria-label], '
                'div[contenteditable="true"][data-testid*="input"], '
                'div[contenteditable="true"][role="textbox"], '
                'div[contenteditable="true"], '
                'textarea'
            )
            el = await self.page.wait_for_selector(input_sel, timeout=8000)
            await el.click()
            tag = await el.evaluate("el => el.tagName.toLowerCase()")
            if tag == "textarea":
                await el.fill(prompt)
            else:
                await self.page.keyboard.type(prompt, delay=10)
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
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()
        stable_needed = 3.0

        while asyncio.get_running_loop().time() < deadline:
            try:
                # Try multiple known Grok response container selectors
                current = await self._collect_last_in(
                    '[data-testid="bot-message"], '
                    '[data-testid="message"]:not([data-testid*="user"]), '
                    'div[class*="GrokMessage"], div[class*="AssistantMessage"], '
                    'article[class*="message"]',
                    'p, span[class*="Text"], div[class*="prose"]'
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
