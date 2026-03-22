"""Onboarding state management — ~/.chorus/onboarding.json."""
import json
from datetime import datetime, timezone
from pathlib import Path

ALL_PLATFORMS = [
    "gemini", "chatgpt", "claude", "perplexity",
    "grok", "copilot", "deepseek", "mistral",
    "meta_ai", "huggingchat",
]

_DEFAULT_STATE = {p: {"status": "pending"} for p in ALL_PLATFORMS}


def load_state(state_file: Path | None = None) -> dict:
    if state_file is None:
        state_file = Path.home() / ".chorus" / "onboarding.json"
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            # Ensure all platforms present (handles new platforms added in updates)
            for p in ALL_PLATFORMS:
                if p not in data:
                    data[p] = {"status": "pending"}
            return data
        except Exception:
            pass
    return {p: {"status": "pending"} for p in ALL_PLATFORMS}


def _save_state(state: dict, state_file: Path) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def mark_completed(platform: str, state_file: Path | None = None) -> None:
    if state_file is None:
        state_file = Path.home() / ".chorus" / "onboarding.json"
    state = load_state(state_file)
    state[platform] = {
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_state(state, state_file)


def mark_skipped(platform: str, state_file: Path | None = None) -> None:
    if state_file is None:
        state_file = Path.home() / ".chorus" / "onboarding.json"
    state = load_state(state_file)
    state[platform] = {"status": "skipped"}
    _save_state(state, state_file)


def needs_onboarding(state_file: Path | None = None) -> bool:
    """Returns True if zero platforms have status='completed'.
    First-launch gate: once ANY platform is completed the wizard
    stops auto-triggering. Users can always re-open via Manage Accounts."""
    state = load_state(state_file)
    return not any(v.get("status") == "completed" for v in state.values())
