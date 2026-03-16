import asyncio
from urllib.parse import quote
from .base import BaseAI


class Gemini(BaseAI):
    name  = "Gemini"
    url   = "https://gemini.google.com/app"
    color = "#4285F4"
    icon  = "🌀"

    async def submit_prompt(self, prompt: str) -> None:
        encoded = quote(prompt)
        await self.page.goto(f"{self.url}?q={encoded}", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        # If URL param didn't auto-submit, find the input and submit manually
        try:
            # Check if response is already being generated
            await self.page.wait_for_selector(
                '[data-response-index], .response-content, model-response',
                timeout=5000
            )
        except Exception:
            # Need to type and submit manually
            try:
                input_sel = 'rich-textarea div[contenteditable="true"], textarea[placeholder], .ql-editor'
                el = await self.page.wait_for_selector(input_sel, timeout=10000)
                await el.click()
                await self.page.keyboard.type(prompt, delay=15)
                await asyncio.sleep(0.5)
                await self.page.keyboard.press("Enter")
            except Exception as e:
                raise RuntimeError(f"Gemini: could not submit prompt — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(2)
        deadline = asyncio.get_event_loop().time() + timeout

        response_sel = "model-response .markdown, .response-content .markdown, " \
                       "[data-response-index] p, model-response p"

        last_text = ""
        stable_since = asyncio.get_event_loop().time()
        stable_needed = 3.0

        while asyncio.get_event_loop().time() < deadline:
            try:
                elements = await self.page.query_selector_all(response_sel)
                if elements:
                    texts = []
                    for el in elements[-1:]:  # last response block
                        t = await el.text_content()
                        if t:
                            texts.append(t.strip())
                    current = "\n".join(texts)
                    if current and current != last_text:
                        last_text = current
                        stable_since = asyncio.get_event_loop().time()
                    elif current and (asyncio.get_event_loop().time() - stable_since) > stable_needed:
                        return current
            except Exception:
                pass
            await asyncio.sleep(0.8)

        return last_text or "[No response captured]"
