import asyncio
from .base import BaseAI


class Gemini(BaseAI):
    name         = "Gemini"
    url          = "https://gemini.google.com/app"
    color        = "#4285F4"
    icon         = "🌀"
    platform_key = "gemini"

    async def submit_prompt(self, prompt: str) -> None:
        await self.page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        await self.assert_authenticated()

        try:
            el = await self.page.wait_for_selector(self._input_sel(), timeout=15000)
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
            raise RuntimeError(f"Gemini: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()
        stable_needed = 3.5

        while asyncio.get_running_loop().time() < deadline:
            try:
                current = await self._collect_blocks()
                if current != last_text:
                    last_text = current
                    stable_since = asyncio.get_running_loop().time()
                elif current and (asyncio.get_running_loop().time() - stable_since) > stable_needed:
                    return current
            except Exception:
                pass
            await asyncio.sleep(0.8)

        if not last_text:
            last_text = await self._js_extract()
        return last_text or "[No response captured]"
