import asyncio
from .base import BaseAI


class Perplexity(BaseAI):
    name         = "Perplexity"
    url          = "https://perplexity.ai"
    color        = "#20b8cd"
    icon         = "🔭"
    platform_key = "perplexity"

    # Response selectors for 2025 Perplexity UI
    # NOTE: avoid bare .prose p — it matches the question display at the top of results
    _RESPONSE_SELS = (
        "div[data-testid='ppl-response'] p, "
        "[data-testid*='answer-text'] p, "
        "[class*='markdown'] p, "
        "[class*='prose']:not([class*='question']):not([class*='nav']):not([class*='tab']) p"
    )

    # Input selectors covering all known Perplexity UI variants
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
                blocks = await self.page.query_selector_all(self._RESPONSE_SELS)
                if blocks:
                    texts = [await b.text_content() or "" for b in blocks]
                    # Strip source/footnote list items (Perplexity appends numbered sources)
                    raw = "\n".join(t.strip() for t in texts if len(t.strip()) > 40 and not t.strip().startswith(("http", "www")))
                    current = raw
                else:
                    current = ""
                if current and len(current) < 15:
                    current = ""  # too short — streaming artifact or question label
                if current != last_text:
                    last_text = current
                    stable_since = asyncio.get_running_loop().time()
                elif current and (asyncio.get_running_loop().time() - stable_since) > stable_needed:
                    return current
            except Exception:
                pass
            await asyncio.sleep(0.8)

        if not last_text:
            # Scoped JS fallback: look inside known answer containers and require
            # substantial paragraphs (> 60 chars) to skip UI chrome labels.
            try:
                last_text = await self.page.evaluate(
                    """(promptSnippet) => {
                        const containers = document.querySelectorAll(
                            '[class*="answer"], [class*="Answer"], [data-testid*="answer"], ' +
                            'div[data-testid="ppl-response"], [class*="result"], [class*="markdown"], ' +
                            '[class*="prose"]'
                        );
                        const seen = new Set();
                        const texts = [];
                        containers.forEach(c => {
                            c.querySelectorAll('p').forEach(p => {
                                const t = p.textContent.trim();
                                if (t.length > 60 && !seen.has(t) &&
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
        return self._clean_response(last_text) or "[No response captured]"
