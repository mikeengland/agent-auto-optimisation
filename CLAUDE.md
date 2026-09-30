# CLAUDE.md

Example project: user feedback on an AI agent becomes eval cases, and a coding agent then optimises the agent
against the whole suite. The agent is the **Grindstone data assistant**, which answers business questions
about a fictional UK coffee roaster by writing SQL against `app/data/shop.db`.

## Layout

- `app/agent.py`: the Pydantic AI agent (structured `AgentAnswer` output, `run_sql` tool, schema injected into instructions).
- `app/prompts/system.md`: the system prompt.
- `app/tools.py`: read-only SQL helpers.
- `app/server.py`, `app/static/index.html`, `app/feedback.py`: web UI, run log, feedback → GitHub issue.
- `app/data/seed.py`: deterministic data generator. `shop.db` is committed; don't regenerate or modify it.
- `evals/dataset.yaml`: the eval suite (Pydantic Evals). `evals/evaluators.py`: custom evaluators. `evals/run.py`: runner.
- `scripts/`: guard checks used by CI, plus `sql.py` for ad-hoc queries.
- `.github/workflows/optimise.yml`: feedback issue → Claude Code → guards → PR. `.github/prompts/optimise.md` is the task prompt.

## Commands

```bash
uv sync                                                      # install
uv run pytest -q                                             # unit tests, no API calls
uv run python -m evals.run                                   # full eval suite, 3 runs per case (costs money)
uv run python -m evals.run --cases a,b --repeat 1            # subset
uv run python scripts/sql.py "SELECT COUNT(*) FROM orders"   # query the data directly
uv run python -m app.agent "How many orders last month?"     # ask the agent once
uv run uvicorn app.server:app --reload                       # web UI on :8000
```

LLM calls need `ANTHROPIC_API_KEY` (or `AGENT_ANTHROPIC_API_KEY`). `AGENT_MODEL=test` runs offline with a dummy model.

## Rules when optimising the agent

- **Evals are append-only.** Never edit or delete an existing case in `evals/dataset.yaml`. Never change
  `evals/run.py`, `evals/evaluators.py`, `tests/`, `scripts/`, `.github/` or this file. CI rejects the change if you do.
- New cases from feedback: `metadata: {source: feedback, issue: N, note: <rule>, reference_sql: <query>}`.
  `reference_sql` returns the expected value in its first cell, and `tests/test_dataset.py` checks it.
- You may change: `app/prompts/system.md`, `app/agent.py`, `app/tools.py`, and new files under `app/`.
- Fix causes, not symptoms. Never put eval questions or expected answers into the prompt or code.
- Prefer encoding deterministic business rules in code (tools, SQL views, a definitions module) over prose.
- Keep changes minimal and scoped to the reported problem. Don't fix other things you notice.
- Every case in the full suite must pass 3/3 runs before you're done.
