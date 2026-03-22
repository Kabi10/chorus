"""Base class for all AI platform connectors."""
import asyncio
import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from playwright.async_api import Page

SELECTORS_FILE = Path(__file__).parent.parent / "selectors.json"

def _load_selectors() -> dict:
    try:
        return json.loads(SELECTORS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

ALL_SELECTORS: dict = _load_selectors()

# URL fragments that indicate a login / auth wall
_AUTH_URL_KEYWORDS = [
    "login", "signin", "sign-in", "sign_in",
    "auth", "signup", "register",
    "accounts.google", "microsoft.com/login",
]


class BaseAI(ABC):
    name:        str = "base"
    url:         str = ""
    color:       str = "#888"
    icon:        str = "🤖"
    platform_key: str = ""   # must match selectors.json key

    def __init__(self, page: Page):
        self.page = page
        self._sel = ALL_SELECTORS.get(self.platform_key, {})
        self._last_prompt: str = ""

    # ── Selector helpers ──────────────────────────────────────────

    def _input_sel(self) -> str:
        return ", ".join(self._sel.get("input", ["textarea"]))

    def _send_sel(self) -> str:
        btns = self._sel.get("send_button", [])
        return ", ".join(btns) if btns else ""

    def _response_sel(self) -> str:
        return ", ".join(self._sel.get("response", [".prose p"]))

    def _auth_sel(self) -> str:
        return ", ".join(self._sel.get("auth_check", []))

    def _loading_sel(self) -> str:
        return ", ".join(self._sel.get("loading_indicator", []))

    # ── Auth / CAPTCHA detection ──────────────────────────────────

    async def check_auth(self) -> bool:
        """Returns True if a login wall or CAPTCHA is detected."""
        url = self.page.url.lower()
        if any(kw in url for kw in _AUTH_URL_KEYWORDS):
            return True
        sel = self._auth_sel()
        if sel:
            try:
                el = await self.page.query_selector(sel)
                return el is not None
            except Exception:
                pass
        return False

    async def assert_authenticated(self):
        """Raise a clear error if not logged in."""
        if await self.check_auth():
            raise RuntimeError(
                f"{self.name}: not logged in. Open Chorus, click ⚙ on {self.name}, "
                f"add an account, and log in once. Current URL: {self.page.url}"
            )

    async def is_authenticated(self) -> bool:
        """Returns True if the user is logged in (inverse of check_auth)."""
        return not await self.check_auth()

    # ── Abstract interface ────────────────────────────────────────

    @abstractmethod
    async def submit_prompt(self, prompt: str) -> None:
        """Navigate to the AI, find the input, type and submit the prompt."""

    @abstractmethod
    async def wait_for_response(self, timeout: int = 90) -> str:
        """Wait until the AI finishes generating and return the full response text."""

    async def run(self, prompt: str, timeout: int = 90) -> str:
        """Full flow: submit + wait. Returns response text."""
        self._last_prompt = prompt
        await self.submit_prompt(prompt)
        return await self.wait_for_response(timeout)

    # ── Convenience helpers ───────────────────────────────────────

    async def _js_click(self, el) -> None:
        """Click via JS evaluate — bypasses Playwright actionability checks (detached DOM, off-screen)."""
        try:
            await el.evaluate("el => el.click()")
        except Exception:
            pass

    async def _type_into(self, selector: str, text: str, use_fill: bool = False):
        el = await self.page.wait_for_selector(selector, timeout=15000)
        try:
            await el.click()
        except Exception:
            await self._js_click(el)
        if use_fill:
            await el.fill(text)
        else:
            await self.page.keyboard.type(text, delay=20)

    async def _wait_stable(self, selector: str, stable_ms: int = 2500, timeout: int = 90) -> str:
        deadline = asyncio.get_running_loop().time() + timeout
        last_text = ""
        stable_since = asyncio.get_running_loop().time()

        while asyncio.get_running_loop().time() < deadline:
            try:
                el = await self.page.query_selector(selector)
                if el:
                    current = (await el.text_content() or "").strip()
                    if current != last_text:
                        last_text = current
                        stable_since = asyncio.get_running_loop().time()
                    elif current and (asyncio.get_running_loop().time() - stable_since) > (stable_ms / 1000):
                        return current
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return last_text

    async def _collect_blocks(self) -> str:
        """Collect text from all response paragraph blocks using selectors.json."""
        sel = self._response_sel()
        blocks = await self.page.query_selector_all(sel)
        if not blocks:
            return ""
        texts = [await b.text_content() or "" for b in blocks]
        return "\n".join(t.strip() for t in texts if t.strip())

    async def _collect_last_in(self, container_sel: str, content_sel: str) -> str:
        """
        Find ALL elements matching container_sel, take the LAST one, then
        collect text from content_sel elements within it.
        Falls back to the container's full textContent if content_sel matches nothing.
        Prevents multi-turn repetition by scoping to the most-recent message only.
        """
        try:
            result = await self.page.evaluate(
                """([cSel, pSel]) => {
                    const containers = document.querySelectorAll(cSel);
                    if (!containers.length) return '';
                    const last = containers[containers.length - 1];
                    const blocks = last.querySelectorAll(pSel);
                    if (blocks.length) {
                        return Array.from(blocks)
                            .map(el => el.textContent.trim())
                            .filter(t => t.length > 0)
                            .join('\\n');
                    }
                    return last.textContent.trim();
                }""",
                [container_sel, content_sel],
            )
            return (result or "").strip()
        except Exception:
            return ""

    def _clean_response(self, text: str) -> str:
        """
        Post-process collected response text to remove common garbage:
        - <think>…</think> blocks (DeepSeek R1 reasoning leaked as text)
        - Sources / References / Citations sections appended by Perplexity et al.
        - Inline citation markers [1], [^2]
        - Consecutive duplicate paragraphs (streaming artifacts / multi-turn bleed)
        """
        if not text:
            return text

        # Strip Grok web-search preamble: "Searching the webN results"
        text = re.sub(r"^Searching the web\s*\d*\s*results?\s*", "", text, flags=re.IGNORECASE)

        # Strip prompt text if it leaked to the start of the response
        if self._last_prompt:
            snippet = self._last_prompt[:50]
            if text.startswith(snippet):
                text = text[len(self._last_prompt):].lstrip()

        # Strip <think>…</think> blocks
        text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)

        # Cut off sources/references section when it appears as a standalone heading
        text = re.sub(
            r"\n{0,2}\*{0,2}(Sources|References|Citations|Bibliography|Further Reading)"
            r"\*{0,2}[\s:]*\n[\s\S]*$",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # Remove inline citation markers like [1], [^2], [12], and Perplexity's +3 style
        text = re.sub(r"\s*\[\^?\d+\]", "", text)
        text = re.sub(r"\s*\+\d+\b", "", text)  # Perplexity "+3" citation counts

        # Strip trailing source-citation lines like "Some Title - domain.com"
        # or "Some Title | source.com" appended by Copilot / Perplexity
        lines_pre = text.split("\n")
        cleaned_lines = []
        for line in lines_pre:
            stripped = line.strip()
            # Skip lines that look like "Article Title - domain.com" or end with a bare domain
            if re.search(r"[-|]\s+\w[\w.-]+\.(com|org|io|net|ai|dev|co)\s*$", stripped, re.IGNORECASE):
                continue
            if re.match(r"^https?://", stripped):
                continue
            cleaned_lines.append(line)
        text = "\n".join(cleaned_lines)

        # Deduplicate consecutive identical lines (streaming / multi-turn bleed)
        lines = text.split("\n")
        out, prev = [], None
        for line in lines:
            stripped = line.strip()
            if stripped and stripped == prev:
                continue
            out.append(line)
            if stripped:
                prev = stripped

        # Collapse runs of 3+ blank lines
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(out))
        return text.strip()

    async def _js_extract(self) -> str:
        """
        JavaScript-based fallback response extraction.
        Collects all paragraph-like text on the page and strips out the
        user's own prompt, returning whatever remains. Works regardless
        of which CSS class names the platform currently uses.
        """
        prompt_snippet = self._last_prompt[:60] if self._last_prompt else ""
        try:
            result = await self.page.evaluate(
                """(promptSnippet) => {
                    // Known garbage patterns from various platform UIs
                    const GARBAGE = ['cookie', 'Cookie Policy', 'privacy policy', 'We use cookies',
                                     'Sign in to', 'Log in to', 'Create account', 'Terms of Service',
                                     'By continuing', 'Accept all'];
                    // Try specific selectors first, fall back to broader scan of main content
                    const specific = document.querySelectorAll(
                        'p, [role="paragraph"], .markdown p, ' +
                        'main p, article p, [role="main"] p, ' +
                        '[class*="message"] p, [class*="response"] p'
                    );
                    let candidates = Array.from(specific);
                    // If very few results, also try div/span text blocks in main area
                    if (candidates.length < 3) {
                        const broad = document.querySelectorAll('main *, article *, [role="main"] *');
                        candidates = [...candidates, ...Array.from(broad)];
                    }
                    const seen = new Set();
                    return candidates
                        .map(el => el.textContent.trim())
                        .filter(t => {
                            if (t.length < 15 || seen.has(t)) return false;
                            if (GARBAGE.some(g => t.includes(g))) return false;
                            if (promptSnippet && t.includes(promptSnippet.substring(0, 30))) return false;
                            seen.add(t);
                            return true;
                        })
                        .join('\\n');
                }""",
                prompt_snippet,
            )
            return (result or "").strip()
        except Exception:
            return ""
