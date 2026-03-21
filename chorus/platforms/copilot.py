import asyncio
from .base import BaseAI


class Copilot(BaseAI):
    name         = "Copilot"
    url          = "https://copilot.microsoft.com"
    color        = "#0078d4"
    icon         = "🪟"
    platform_key = "copilot"

    def __init__(self, page):
        super().__init__(page)
        self._last_prompt = ""

    async def submit_prompt(self, prompt: str) -> None:
        self._last_prompt = prompt
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

    async def _js_extract(self) -> str:
        """
        JavaScript fallback: collect all paragraph-like text on the page,
        strip out the user's own prompt, and return what remains.
        Works regardless of which CSS class names Copilot uses.
        """
        try:
            prompt_snippet = self._last_prompt[:60]
            result = await self.page.evaluate(
                """(promptSnippet) => {
                    const candidates = Array.from(
                        document.querySelectorAll('p, [role="paragraph"], li, .ac-textBlock')
                    );
                    return candidates
                        .map(el => el.textContent.trim())
                        .filter(t => t.length > 20 && !t.startsWith(promptSnippet))
                        .join('\\n');
                }""",
                prompt_snippet,
            )
            return (result or "").strip()
        except Exception:
            return ""

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()
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
            '[role="presentation"] p'
        )

        while asyncio.get_running_loop().time() < deadline:
            try:
                # Try scoping to the last bot message container first
                current = await self._collect_last_in(
                    'cib-chat-turn[source="bot"], [data-testid*="bot-message"], [class*="BotMessage"]',
                    'p, .ac-textBlock'
                )
                if not current:
                    blocks = await self.page.query_selector_all(response_sels)
                    if blocks:
                        texts = [await b.text_content() or "" for b in blocks]
                        current = "\n".join(t.strip() for t in texts if t.strip())
                    else:
                        current = await self._js_extract()

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
