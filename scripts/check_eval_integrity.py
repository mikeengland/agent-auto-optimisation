"""Guard: make sure an optimisation branch didn't make the evals easier to pass.

Checks, against a base git ref (default origin/main):
  1. Every eval case that exists on the base is still present and byte-for-byte identical.
  2. The grading machinery (eval runner, evaluators, tests, CI, guard scripts) is untouched.
  3. With --require-new: at least one new case was added (with --issue N: tagged with that issue).

Prints the names of new cases (comma-separated) on the last line of stdout so CI can pass them on.

    uv run python scripts/check_eval_integrity.py --base origin/main --require-new --issue 12
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

DATASET = "evals/dataset.yaml"
PROTECTED = ["evals/run.py", "evals/evaluators.py", "evals/__init__.py", "scripts/", "tests/", ".github/", "CLAUDE.md"]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def cases_by_name(text: str) -> dict[str, dict]:
    return {c["name"]: c for c in (yaml.safe_load(text) or {}).get("cases", [])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--require-new", action="store_true")
    parser.add_argument("--issue", type=int)
    args = parser.parse_args()

    errors: list[str] = []
    base_cases = cases_by_name(git("show", f"{args.base}:{DATASET}"))
    head_cases = cases_by_name(Path(DATASET).read_text())

    for name, case in base_cases.items():
        if name not in head_cases:
            errors.append(f"existing eval case `{name}` was removed")
        elif head_cases[name] != case:
            errors.append(f"existing eval case `{name}` was modified")

    changed = git("diff", "--name-only", args.base, "--").splitlines()
    changed += git("ls-files", "--others", "--exclude-standard").splitlines()
    for path in sorted(set(changed)):
        if any(path == p or (p.endswith("/") and path.startswith(p)) for p in PROTECTED):
            errors.append(f"protected file `{path}` was changed")

    new = [n for n in head_cases if n not in base_cases]
    if args.require_new and not new:
        errors.append("no new eval case was added")
    for name in new:
        meta = head_cases[name].get("metadata") or {}
        if args.issue is not None and meta.get("issue") != args.issue:
            errors.append(f"new case `{name}` should have metadata.issue: {args.issue}")

    if errors:
        print("Eval integrity check FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"Eval integrity OK: {len(base_cases)} existing case(s) unchanged, {len(new)} new: {', '.join(new) or '-'}")
    print(",".join(new))
    return 0


if __name__ == "__main__":
    sys.exit(main())
