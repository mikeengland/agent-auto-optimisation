# Agent auto-optimisation from human feedback

A small, working example of a loop where **human feedback on an AI agent becomes an optimisation target**:

1. A user asks the agent a question and gets a wrong answer. They click 👎 and say what was wrong.
2. The feedback becomes a **GitHub issue**, with the question, the answer, the agent's full SQL trace and the correction.
3. A **GitHub Action** starts **Claude Code**. It turns the feedback into **new eval cases**, confirms they fail,
   then changes the agent's prompt and/or tools until the new cases **and every existing case** pass.
4. Guard steps that the coding agent can't influence re-check the work, and the workflow opens a **pull request**
   explaining the old behaviour, the fix and the before/after eval results.
5. A human reviews and merges. The suite keeps the new cases, so every piece of feedback raises the minimum
   standard for the next change.

```
👎 feedback ──▶ issue ──▶ Claude Code: write eval ▸ prove it fails ▸ fix prompt/tools ▸ all evals green
                                             ──▶ guards (evals untouched? fails on main? suite green?) ──▶ PR ──▶ human review
```

## The example agent

The **Grindstone data assistant** answers business questions about a fictional UK online coffee roaster.
It's a [Pydantic AI](https://ai.pydantic.dev) agent that writes SQL against a seeded SQLite database and returns a
structured answer. Evals use [Pydantic Evals](https://ai.pydantic.dev/evals/), with the dataset in
`evals/dataset.yaml`, so each new eval shows up as a readable diff in the PR.

The data contains business rules that the schema doesn't reveal, so the agent reliably gets them wrong until
someone tells it. These are the demo scenarios:

| Ask this | The agent will... | Feedback to give | Correct answer |
|---|---|---|---|
| What was our revenue in May 2026? | sum every order | Revenue excludes cancelled orders and is net of refunds (the `refunds` table), attributed to the order date. | **£10,999** |
| How many orders did we receive in Q1? | use Jan–Mar 2026 | Our financial year starts on 1 April, so Q1 is April–June. We're in FY2026/27. | **853** |
| How many customers do we have? | count everyone | Staff/QA test accounts (emails ending `@grindstonecoffee.co.uk`) aren't customers. | **600** |

The existing suite has traps for lazy fixes. For example, "How many orders were placed in May?" must still count
cancelled orders. So "just ignore cancelled orders everywhere" breaks an existing eval.

## Run it locally

```bash
uv sync
uv run pytest -q                              # offline unit tests
export ANTHROPIC_API_KEY=sk-ant-...           # pay-as-you-go key for the app agent
uv run python -m evals.run                    # baseline suite should be all green
uv run uvicorn app.server:app --reload        # UI at http://localhost:8000
```

Without GitHub configured, 👎 feedback is saved to `runs/feedback-<id>.md`. You can run the optimiser on it
locally with `scripts/optimise_local.sh runs/feedback-<id>.md` (needs the `claude` CLI).

To have the UI create real issues, also set `GITHUB_TOKEN` (a fine-grained PAT with *Issues: read & write*
on this repo) and `GITHUB_REPOSITORY=owner/repo`.

## GitHub setup

Repository **secrets**:

| Secret | What for |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code in the workflow, on your Claude subscription. Create it with `claude setup-token`. |
| `AGENT_ANTHROPIC_API_KEY` | The app agent while evals run (API key from console.anthropic.com). It deliberately isn't named `ANTHROPIC_API_KEY`, so that Claude Code doesn't bill the API instead of your subscription. |
| `GH_PAT` *(optional)* | Fine-grained PAT (contents, pull requests, issues: write). If set, PRs opened by the workflow also trigger the `Evals` workflow. PRs opened with the default token don't. |

Then in **Settings → Actions → General**, enable *Allow GitHub Actions to create and approve pull requests*.

The optimise workflow only starts for issues labelled `agent-feedback` **and** opened by the repository owner
(the account behind the UI's token). You can re-run it for any issue from the Actions tab (`workflow_dispatch`).

## Safety checks

The coding agent is optimising against the evals, and it can edit the evals. So the workflow re-checks its
work independently before a PR is marked ready:

1. **Existing evals untouched:** existing cases in `dataset.yaml`, the evaluators, the runner, the tests and
   CI are byte-for-byte unchanged. Cases may only be appended.
2. **Expected values match the data:** each numeric case has a `reference_sql`, and the tests check that it
   gives the expected answer.
3. **New evals fail on `main`:** proves the eval actually captures the reported problem.
4. **Full suite passes on the branch:** 3 runs per case, all must pass, because LLM output varies.

If any check fails, the PR is opened as a draft. Claude also writes variant cases (the same rule on different
inputs) to discourage fixes that only memorise one answer.

## Cost

With Claude Haiku 4.5 as the app agent, a full suite run (≈10 cases × 3 runs) should cost well under a dollar
(an estimate, not yet measured).
The optimisation prompt caps Claude at 4 full-suite runs per issue. Change the app model with `AGENT_MODEL`.
