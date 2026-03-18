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
        await asyncio.sleep(5)  # ChatGPT React app needs time to render
        await self.assert_authenticated()

        try:
            el = await self.page.wait_for_selector(self._input_sel(), timeout=20000)
            await el.click()
            tag = await el.evaluate("el => el.tagName.toLowerCase()")
            if tag == "textarea":
                await el.fill(prompt)
            else:
                await self.page.keyboard.type(prompt, delay=10)
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
            raise RuntimeError(f"ChatGPT: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_event_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_event_loop().time()
        stable_needed = 3.0

        while asyncio.get_event_loop().time() < deadline:
            try:
                loading = await self.page.query_selector(self._loading_sel()) if self._loading_sel() else None
                current = await self._collect_blocks()
                if current != last_text:
                    last_text = current
                    stable_since = asyncio.get_event_loop().time()
                elif current and not loading and (asyncio.get_event_loop().time() - stable_since) > stable_needed:
                    return current
            except Exception:
                pass
            await asyncio.sleep(0.8)

        return last_text or "[No response captured]"
