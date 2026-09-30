import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "app" / "data" / "shop.db"
PROMPT_PATH = ROOT / "app" / "prompts" / "system.md"

# The model the *app agent* runs on (not the coding agent that optimises it).
AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude-haiku-4-5")

# The data is a fixed snapshot, so "today" is pinned to keep relative dates ("last month") reproducible.
TODAY = date(2026, 9, 1)


def anthropic_api_key() -> str | None:
    # AGENT_ANTHROPIC_API_KEY takes priority so that CI can give the app agent a pay-as-you-go API key
    # without Claude Code (which runs on a subscription token) picking it up as its own credential.
    return os.environ.get("AGENT_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
