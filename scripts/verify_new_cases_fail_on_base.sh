#!/usr/bin/env bash
# Guard: the new eval case(s) must FAIL against the base branch's agent.
# If they already pass, they don't capture the problem that was reported.
#
#   scripts/verify_new_cases_fail_on_base.sh <base-ref> <comma-separated-case-names>
set -euo pipefail

BASE_REF="$1"
CASES="$2"
REPEAT="${EVAL_REPEAT:-3}"
REPO="$(pwd)"
WORKTREE="$(mktemp -d)/base"
mkdir -p .optimise

git worktree add --detach "$WORKTREE" "$BASE_REF" >/dev/null
trap 'git worktree remove --force "$WORKTREE"' EXIT

# Base agent code + the branch's eval suite.
rm -rf "$WORKTREE/evals"
cp -r evals "$WORKTREE/evals"

cd "$WORKTREE"
echo "Running new case(s) [$CASES] against $BASE_REF (expecting failure)..."
# Reuse this checkout's virtualenv; `-m` puts the worktree (base code) first on sys.path.
"$REPO/.venv/bin/python" -m evals.run --cases "$CASES" --repeat "$REPEAT" --expect-fail \
  --markdown "$REPO/.optimise/base_results.md"
