import asyncio
from .base import BaseAI


class Perplexity(BaseAI):
    name         = "Perplexity"
    url          = "https://perplexity.ai"
    color        = "#20b8cd"
    icon         = "🔭"
    platform_key = "perplexity"

    _INPUT_SELS = (
        "textarea[placeholder*='Ask'], "
        "textarea[placeholder*='Search'], "
        "textarea[name='q'], "
        "div[contenteditable='true'][placeholder*='Ask'], "
        "div[contenteditable='true'][role='textbox'], "
        "div[contenteditable='true'], "
        "textarea"
    )

    async def submit_prompt(self, prompt: str) -> None:
        await self.page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)
        await self.assert_authenticated()

        try:
            el = await self.page.wait_for_selector(self._INPUT_SELS, timeout=15000)
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
            raise RuntimeError(f"Perplexity: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(3)
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()
        stable_needed = 3.5

        while asyncio.get_running_loop().time() < deadline:
            try:
                # Scope to answer containers — avoid nav/tab labels
                current = await self._collect_last_in(
                    '[class*="answer"], [data-testid*="answer"], '
                    '[class*="Answer"], [class*="result-content"], '
                    '[class*="prose"]:not(nav *):not(header *)',
                    'p, li'
                )
                # Fallback: try markdown containers specifically
                if not current:
                    current = await self._collect_last_in(
                        '[class*="markdown"]',
                        'p, li'
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
            # JS fallback scoped to answer containers
            try:
                last_text = await self.page.evaluate(
                    """(promptSnippet) => {
                        const containers = document.querySelectorAll(
                            '[class*="answer"], [class*="Answer"], [data-testid*="answer"], ' +
                            '[class*="result"], [class*="markdown"], [class*="prose"]'
                        );
                        const seen = new Set();
                        const texts = [];
                        containers.forEach(c => {
                            // Skip nav-like containers
                            if (c.closest('nav, header, footer, [role="navigation"]')) return;
                            c.querySelectorAll('p, li').forEach(p => {
                                const t = p.textContent.trim();
                                if (t.length > 2 && !seen.has(t) &&
                                    !t.startsWith('http') && !t.startsWith('www') &&
                                    !(promptSnippet && t.includes(promptSnippet.substring(0, 30)))) {
                                    seen.add(t);
                                    texts.push(t);
                                }
                            });
                        });
                        return texts.join('\\n');
                    }""",
                    self._last_prompt[:60]
                ) or ""
            except Exception:
                last_text = ""
        if not last_text:
            last_text = await self._js_extract()
        if not last_text:
            last_text = await self._body_text_extract()
        return self._clean_response(last_text) or "[No response captured]"
