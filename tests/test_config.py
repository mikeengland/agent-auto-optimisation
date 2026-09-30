import importlib

from app import agent, config


def test_empty_anthropic_base_url_falls_back_to_default(monkeypatch):
    # Claude Code's GitHub Action exports ANTHROPIC_BASE_URL="" into the commands it runs.
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "")
    monkeypatch.setenv("AGENT_ANTHROPIC_API_KEY", "sk-ant-test")
    importlib.reload(config)
    try:
        assert config.ANTHROPIC_BASE_URL == "https://api.anthropic.com"
        assert str(agent.build_model().client.base_url).startswith("https://api.anthropic.com")
    finally:
        monkeypatch.undo()
        importlib.reload(config)
