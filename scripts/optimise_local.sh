#!/usr/bin/env bash
# Run the optimisation loop locally with Claude Code instead of in GitHub Actions.
#
#   scripts/optimise_local.sh runs/feedback-<id>.md [issue-number]
#
# Needs the `claude` CLI (logged in) and ANTHROPIC_API_KEY / AGENT_ANTHROPIC_API_KEY for the app agent.
# Then run the same guards the workflow runs:
#   uv run python scripts/check_eval_integrity.py --base main --require-new
#   scripts/verify_new_cases_fail_on_base.sh main <new-case-names>
#   uv run python -m evals.run
set -euo pipefail

FEEDBACK="$1"
export ISSUE="${2:-0}"
mkdir -p .optimise
{ echo "# Issue #$ISSUE (local run)"; echo; cat "$FEEDBACK"; } > .optimise/feedback.md

claude -p "Follow the instructions in .github/prompts/optimise.md. The feedback to act on is issue #$ISSUE, saved in .optimise/feedback.md." \
  --allowedTools "Read,Edit,Write,Glob,Grep,Bash(uv run:*),Bash(git diff:*),Bash(git status:*),Bash(git log:*),Bash(git show:*)"

cat .optimise/outcome.json
