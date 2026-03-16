# Contributing to Chorus

Thanks for your interest in improving Chorus!

## Ways to contribute

- **New AI platform connectors** — the most impactful contribution
- **Better selectors** — AI UIs change frequently; selector fixes are always welcome
- **UI improvements** — all frontend is in `frontend/index.html`
- **Consensus engine** — improve the keyword analysis or add NLP-based analysis
- **Bug fixes and docs**

## Setup

```bash
git clone https://github.com/Kabi10/chorus.git
cd chorus
pip install -r requirements.txt
playwright install chromium
python main.py
```

## Adding a new AI platform

1. Create `chorus/platforms/myai.py`:

```python
import asyncio
from .base import BaseAI

class MyAI(BaseAI):
    name  = "My AI"
    url   = "https://myai.example.com"
    color = "#ff0000"
    icon  = "🤖"

    async def submit_prompt(self, prompt: str) -> None:
        await self.page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        # find input, fill, submit
        el = await self.page.wait_for_selector("textarea", timeout=10000)
        await el.fill(prompt)
        await self.page.keyboard.press("Enter")

    async def wait_for_response(self, timeout: int = 90) -> str:
        # poll selector until stable
        return await self._wait_stable(".response-container", stable_ms=3000, timeout=timeout)
```

2. Register in `main.py`:

```python
from chorus.platforms.myai import MyAI

PLATFORMS["myai"] = MyAI
PLATFORM_META["myai"] = {"name": "My AI", "color": "#ff0000", "icon": "🤖"}
```

That's it — the frontend discovers it automatically via `/api/platforms`.

## Selector maintenance

AI platforms update their UI frequently. If a platform stops working:

1. Open the platform in a browser
2. Inspect the input element and response container
3. Update the selectors in the platform file
4. Open a PR with the fix

## Code style

- Python: PEP 8, async throughout
- JavaScript: vanilla ES2020+, no frameworks
- Keep `main.py` and `frontend/index.html` as single-file architecture

## Submitting a PR

1. Fork the repo
2. Create a branch: `git checkout -b fix/platform-selector`
3. Test locally with `python main.py`
4. Open a pull request describing what changed and why

## Issues

Use GitHub Issues for:
- Platform connector broken (include which platform and approximate date)
- Feature requests
- Bug reports (include OS, Python version, error message)
