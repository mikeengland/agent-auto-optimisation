"""Turn a piece of user feedback on an agent run into a GitHub issue.

The issue is the hand-off to the optimisation workflow (.github/workflows/optimise.yml), which is
triggered by issues labelled `agent-feedback`. The body carries everything the coding agent needs:
the question, what the agent answered, its full SQL trace, and what the user says was wrong.

If GITHUB_TOKEN / GITHUB_REPOSITORY aren't set, the issue is written to runs/ instead (a dry run).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import httpx
from pydantic import BaseModel

from app import config

FEEDBACK_LABEL = "agent-feedback"
RUNS_DIR = config.ROOT / "runs"


class Feedback(BaseModel):
    run_id: str
    what_was_wrong: str
    expected_answer: str | None = None
    expected_value: float | None = None


def app_commit() -> str:
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=config.ROOT)
    return out.stdout.strip() or "unknown"


def render_issue(run: dict, feedback: Feedback) -> tuple[str, str]:
    question = run["question"]
    output = run["output"]
    title = f"Agent feedback: {question[:80]}"

    trace = []
    for i, step in enumerate(run["steps"], start=1):
        query = step["args"].get("query", json.dumps(step["args"]))
        trace.append(f"**{i}. `{step['tool']}`**\n\n```sql\n{query}\n```\n\n```\n{step['result'][:1500]}\n```")
    trace_md = "\n\n".join(trace) or "_The agent made no tool calls._"

    expected = feedback.expected_answer or "_not given_"
    if feedback.expected_value is not None:
        expected += f" (value: `{feedback.expected_value:g}`)"

    machine = {
        "run_id": run["id"],
        "question": question,
        "agent_output": output,
        "what_was_wrong": feedback.what_was_wrong,
        "expected_answer": feedback.expected_answer,
        "expected_value": feedback.expected_value,
        "app_commit": run.get("app_commit"),
        "model": run.get("model"),
    }

    body = f"""## 👎 Feedback on the data assistant

**Question:** {question}

**Agent answered:** {output['answer']}
(value: `{output.get('value')}`, status: `{output['status']}`)

**What was wrong (from the user):**
> {feedback.what_was_wrong.strip().replace(chr(10), chr(10) + '> ')}

**Expected answer:** {expected}

<details><summary>Agent trace ({len(run['steps'])} tool call(s))</summary>

{trace_md}

</details>

<details><summary>Machine-readable feedback</summary>

```json
{json.dumps(machine, indent=2)}
```

</details>

---
_Submitted from the data assistant UI · app commit `{run.get('app_commit')}` · model `{run.get('model')}`.
The `optimise` workflow will turn this into an eval case and open a PR with a fix._
"""
    return title, body


def create_issue(run: dict, feedback: Feedback) -> dict:
    title, body = render_issue(run, feedback)
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not (token and repo):
        path = RUNS_DIR / f"feedback-{run['id']}.md"
        path.write_text(f"# {title}\n\n{body}")
        return {"dry_run": True, "path": str(path.relative_to(config.ROOT))}

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    with httpx.Client(base_url=f"https://api.github.com/repos/{repo}", headers=headers, timeout=30) as gh:
        if gh.get(f"/labels/{FEEDBACK_LABEL}").status_code == 404:
            gh.post("/labels", json={"name": FEEDBACK_LABEL, "color": "d93f0b", "description": "User feedback on the agent"})
        resp = gh.post("/issues", json={"title": title, "body": body, "labels": [FEEDBACK_LABEL]})
        resp.raise_for_status()
        issue = resp.json()
    return {"dry_run": False, "number": issue["number"], "url": issue["html_url"]}


def save_run(run: dict) -> None:
    RUNS_DIR.mkdir(exist_ok=True)
    (RUNS_DIR / f"{run['id']}.json").write_text(json.dumps(run, indent=2))


def load_run(run_id: str) -> dict | None:
    path = RUNS_DIR / f"{Path(run_id).name}.json"
    return json.loads(path.read_text()) if path.exists() else None
