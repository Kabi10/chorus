import asyncio
from .base import BaseAI


class Claude(BaseAI):
    name         = "Claude"
    url          = "https://claude.ai/new"
    color        = "#d97706"
    icon         = "🟣"
    platform_key = "claude"

    async def submit_prompt(self, prompt: str) -> None:
        await self.page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        await self.assert_authenticated()

        try:
            el = await self.page.wait_for_selector(self._input_sel(), timeout=20000)
            await el.click()
            await self.page.keyboard.type(prompt, delay=15)
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
            raise RuntimeError(f"Claude: could not submit — {e}")

    async def wait_for_response(self, timeout: int = 90) -> str:
        await asyncio.sleep(2)
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()
        stable_needed = 3.0

        while asyncio.get_running_loop().time() < deadline:
            try:
                streaming = await self.page.query_selector(self._loading_sel()) if self._loading_sel() else None
                # Scope to LAST assistant message only — try specific selectors
                current = await self._collect_last_in(
                    '[data-testid="assistant-message"], '
                    '[data-testid="assistant-message-content"], '
                    '[data-message-author-role="assistant"], '
                    '.font-claude-message, '
                    '[data-author="assistant"], '
                    'div[class*="AssistantMessage"]',
                    'p, li, [class*="prose"] p, [class*="markdown"] p'
                )
                if current and len(current) < 2:
                    current = ""  # truly empty only — let stability check handle short answers
                if current != last_text:
                    last_text = current
                    stable_since = asyncio.get_running_loop().time()
                elif current and not streaming and (asyncio.get_running_loop().time() - stable_since) > stable_needed:
                    return self._clean_response(current)
            except Exception:
                pass
            await asyncio.sleep(0.8)

        if not last_text:
            # JS fallback — content-based filter: sidebar items are short phrases,
            # real responses are sentences. Collect p/li text > 25 chars only.
            last_text = await self.page.evaluate("""(promptSnippet) => {
                const NAV_EXACT = new Set(["New chat","Search","Customize","Chats",
                    "Projects","Artifacts","Recents","Hide","Claude Code","Settings",
                    "Sign in","Log in","Help & support","What's new"]);
                const NAV_STARTS = ['Terms of','Cookie','Privacy','By continuing',
                    'Accept','Sign in to'];
                const promptStart = promptSnippet.substring(0, 25);

                // 1. Try all known assistant container selectors
                const containerSels = [
                    '[data-testid="assistant-message"]',
                    '[data-testid="assistant-message-content"]',
                    '[data-message-author-role="assistant"]',
                    '.font-claude-message',
                    '[data-author="assistant"]',
                    'div[class*="AssistantMessage"]',
                    'div[class*="assistant-message"]',
                    'div[class*="prose"]',
                ];
                for (const sel of containerSels) {
                    try {
                        const els = document.querySelectorAll(sel);
                        if (!els.length) continue;
                        const el = els[els.length - 1];
                        // Collect text from p/li inside, or direct textContent
                        const inner = Array.from(el.querySelectorAll('p, li'))
                            .map(e => e.textContent.trim())
                            .filter(t => t.length > 10);
                        const text = inner.length ? inner.join('\\n') : el.textContent.trim();
                        if (text.length > 10 && !NAV_EXACT.has(text)
                                && !NAV_STARTS.some(w => text.startsWith(w))
                                && !text.startsWith(promptStart))
                            return text;
                    } catch(e) {}
                }

                // 2. Content-length filter: collect p elements > 25 chars from anywhere in main
                const main = document.querySelector('main, [role="main"], article, body');
                if (main) {
                    const seen = new Set();
                    const kept = Array.from(main.querySelectorAll('p, li'))
                        .map(el => el.textContent.trim())
                        .filter(t => {
                            if (t.length < 50) return false;  // sidebar history titles are 25-35 chars; real responses are longer
                            if (seen.has(t)) return false;
                            if (NAV_EXACT.has(t)) return false;
                            if (NAV_STARTS.some(w => t.startsWith(w))) return false;
                            if (t.startsWith(promptStart)) return false;
                            seen.add(t);
                            return true;
                        });
                    if (kept.length) return kept.join('\\n');
                }
                return '';
            }""", self._last_prompt[:60]) or ""
        return self._clean_response(last_text) or "[No response captured]"
