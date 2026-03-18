import asyncio
from urllib.parse import quote
from .base import BaseAI


class Perplexity(BaseAI):
    name         = "Perplexity"
    url          = "https://perplexity.ai"
    color        = "#20b8cd"
    icon         = "🔭"
    platform_key = "perplexity"

    # Broader response selectors for 2025 Perplexity UI
    _RESPONSE_SELS = (
        ".prose p, "
        "[class*='answer'] p, [class*='Answer'] p, "
        "[data-testid*='answer'] p, "
        "div[data-testid='ppl-response'] p, "
        "[class*='result'] p, .result-block p, "
        "[class*='markdown'] p"
    )

    async def submit_prompt(self, prompt: str) -> None:
        encoded = quote(prompt)
        await self.page.goto(f"{self.url}/?q={encoded}", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)
        await self.assert_authenticated()

        # Check if URL-based submission already triggered a response
        try:
            await self.page.wait_for_selector(self._RESPONSE_SELS, timeout=8000)
            return  # response is loading, wait_for_response will capture it
        except Exception:
            pass

        # Fall back to finding and submitting via the input field
        extended_input_sel = (
            "textarea[placeholder*='Ask'], "
            "textarea[placeholder*='Search'], "
            "textarea[name='q'], "
            "div[contenteditable='true'][placeholder*='Ask'], "
            "div[contenteditable='true'][role='textbox'], "
            "textarea"
        )
        try:
            el = await self.page.wait_for_selector(extended_input_sel, timeout=10000)
            await el.click()
            await el.fill(prompt)
            await asyncio.sleep(0.5)

            send_sel = self._send_sel()
            if send_sel:
                try:
                    btn = await self.page.wait_for_selector(send_sel, timeout=3000)
                    await btn.click()
                    return
                except Exception:
                    pass
            await self.page.keyboard.press("Enter")
        except Exception as e:
            raise RuntimeError(f"Perplexity: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()
        stable_needed = 3.5

        while asyncio.get_running_loop().time() < deadline:
            try:
                blocks = await self.page.query_selector_all(self._RESPONSE_SELS)
                if blocks:
                    texts = [await b.text_content() or "" for b in blocks]
                    current = "\n".join(t.strip() for t in texts if t.strip())
                else:
                    current = await self._collect_blocks()
                if current != last_text:
                    last_text = current
                    stable_since = asyncio.get_running_loop().time()
                elif current and (asyncio.get_running_loop().time() - stable_since) > stable_needed:
                    return current
            except Exception:
                pass
            await asyncio.sleep(0.8)

        return last_text or "[No response captured]"
