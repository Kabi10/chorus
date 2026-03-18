import asyncio
from .base import BaseAI


class Copilot(BaseAI):
    name         = "Copilot"
    url          = "https://copilot.microsoft.com"
    color        = "#0078d4"
    icon         = "🪟"
    platform_key = "copilot"

    async def submit_prompt(self, prompt: str) -> None:
        await self.page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)

        try:
            input_sel = (
                # New Copilot UI (2025)
                'textarea[id="userInput"], '
                'textarea[data-testid*="input"], '
                'div[contenteditable="true"][data-testid*="input"], '
                # Fallbacks
                'textarea[placeholder], '
                'div[contenteditable="true"][aria-label], '
                'textarea'
            )
            el = await self.page.wait_for_selector(input_sel, timeout=15000)
            await el.click()
            tag = await el.evaluate("el => el.tagName.toLowerCase()")
            if tag == "textarea":
                await el.fill(prompt)
            else:
                await self.page.keyboard.type(prompt, delay=10)
            await asyncio.sleep(0.5)

            try:
                send_btn = await self.page.wait_for_selector(
                    'button[aria-label*="Send"], button[aria-label*="Submit"], '
                    'button[data-testid*="send"], '
                    'button[type="submit"]:not([disabled])',
                    timeout=3000
                )
                await send_btn.click()
            except Exception:
                await self.page.keyboard.press("Enter")
        except Exception as e:
            raise RuntimeError(f"Copilot: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_event_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_event_loop().time()
        stable_needed = 3.5

        # All known Copilot response selectors (old cib-* + new React structure)
        response_sels = (
            'cib-chat-turn[source="bot"] p, '
            'cib-message-group[source="bot"] cib-message p, '
            '[data-testid="message-text"] p, '
            '[data-testid*="bot-message"] p, '
            '[class*="BotMessage"] p, '
            '[class*="bot-message"] p, '
            '[class*="response"] p, '
            '.ac-textBlock p, '
            '.prose p, '
            # Broadest fallback — last AI message paragraphs
            '[role="presentation"] p'
        )

        while asyncio.get_event_loop().time() < deadline:
            try:
                blocks = await self.page.query_selector_all(response_sels)
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
