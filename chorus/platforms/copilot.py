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
            try:
                await el.click()
            except Exception:
                await self._js_click(el)
            await asyncio.sleep(0.5)
            try:
                tag = await el.evaluate("el => el.tagName.toLowerCase()")
            except Exception:
                el = await self.page.wait_for_selector(input_sel, timeout=8000)
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
                    timeout=4000
                )
                try:
                    await send_btn.click()
                except Exception:
                    await self._js_click(send_btn)
            except Exception:
                await self.page.keyboard.press("Enter")
        except Exception as e:
            raise RuntimeError(f"Copilot: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()
        stable_needed = 3.5

        while asyncio.get_running_loop().time() < deadline:
            try:
                # Check if Copilot is still streaming
                stop_btn = await self.page.query_selector(
                    'button#stop-responding-button, button[aria-label*="Stop"]'
                )

                current = ""

                # ── Method 1: Shadow DOM (cib-* web components) ──
                # Playwright's query_selector auto-pierces shadow roots,
                # unlike document.querySelectorAll in page.evaluate.
                containers = await self.page.query_selector_all(
                    'cib-message-group[source="bot"]'
                )
                if containers:
                    last = containers[-1]
                    text_blocks = await last.query_selector_all('.ac-textBlock')
                    if text_blocks:
                        texts = [await b.text_content() or "" for b in text_blocks]
                        current = "\n".join(t.strip() for t in texts if t.strip())
                    if not current:
                        current = (await last.text_content() or "").strip()

                # ── Method 2: Non-shadow containers (2025 redesign) ──
                if not current:
                    current = await self._collect_last_in(
                        '[data-testid="message-container"], '
                        '[data-testid*="bot-message"], [class*="BotMessage"], '
                        '[class*="response-message"], [class*="copilot-response"], '
                        '[class*="assistant"]',
                        'p, .ac-textBlock, div[class*="content"], div[class*="markdown"]'
                    )

                # ── Method 3: Broad Playwright query ──
                if not current:
                    for sel in ['.ac-textBlock', '[class*="response"] p',
                                '[class*="bot-message"] p', '.prose p']:
                        blocks = await self.page.query_selector_all(sel)
                        if blocks:
                            texts = [await b.text_content() or "" for b in blocks]
                            joined = "\n".join(t.strip() for t in texts if t.strip())
                            if joined and len(joined) > 2:
                                current = joined
                                break

                # ── Method 4: JS fallback ──
                if not current:
                    current = await self._js_extract()

                if current != last_text:
                    last_text = current
                    stable_since = asyncio.get_running_loop().time()
                elif current and not stop_btn and (asyncio.get_running_loop().time() - stable_since) > stable_needed:
                    return self._clean_response(current)
            except Exception:
                pass
            await asyncio.sleep(0.8)

        if not last_text:
            last_text = await self._js_extract()
        if not last_text:
            last_text = await self._body_text_extract()
        return self._clean_response(last_text) or "[No response captured]"

    async def _js_extract(self) -> str:
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
