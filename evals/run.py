"""Run the eval suite against the agent.

    uv run python -m evals.run                      # full suite, 3 runs per case
    uv run python -m evals.run --cases a,b -r 1     # a subset, one run each
    uv run python -m evals.run --expect-fail --cases new_case   # succeed only if the case(s) FAIL

A case passes only if every one of its runs passes (all assertions true, no errors).
Exit code: 0 if all selected cases pass (or, with --expect-fail, if every selected case fails at least once).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from pydantic_evals import Dataset

from app import config
from app.agent import AgentAnswer, ask
from evals.evaluators import CUSTOM_EVALUATORS, EvalInput

DATASET_PATH = Path(__file__).parent / "dataset.yaml"


def load_dataset(path: Path = DATASET_PATH) -> Dataset[EvalInput, AgentAnswer, dict]:
    return Dataset[EvalInput, AgentAnswer, dict].from_file(path, custom_evaluator_types=CUSTOM_EVALUATORS)


async def task(inputs: EvalInput) -> AgentAnswer:
    return (await ask(inputs.question)).output


@dataclass
class CaseResult:
    name: str
    source: str
    passed_runs: int
    total_runs: int
    details: list[str]

    @property
    def passed(self) -> bool:
        return self.passed_runs == self.total_runs


def summarise(dataset: Dataset, report) -> list[CaseResult]:
    by_case: dict[str, CaseResult] = {}
    for case in dataset.cases:
        source = (case.metadata or {}).get("source", "?")
        issue = (case.metadata or {}).get("issue")
        label = f"{source} #{issue}" if issue else source
        by_case[case.name] = CaseResult(case.name, label, 0, 0, [])

    for run in report.cases:
        result = by_case[run.source_case_name or run.name]
        result.total_runs += 1
        failed = [f"{k}: {v.reason}" for k, v in run.assertions.items() if not v.value]
        failed += [f"{f.name}: {f.error_message}" for f in run.evaluator_failures]
        if failed:
            result.details.extend(failed)
        else:
            result.passed_runs += 1
    for failure in report.failures:
        result = by_case[failure.source_case_name or failure.name]
        result.total_runs += 1
        result.details.append(f"task error: {failure.error_message}")
    return list(by_case.values())


def to_markdown(results: list[CaseResult], repeat: int) -> str:
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    passed = sum(r.passed for r in results)
    lines = [
        f"**{passed}/{len(results)} cases passing** · model `{config.AGENT_MODEL}` · {repeat} run(s) per case"
        + (f" · commit `{sha}`" if sha else ""),
        "",
        "| | Case | Source | Runs passed | Detail |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        icon = "✅" if r.passed else "❌"
        detail = r.details[0].replace("|", "\\|").replace("\n", " ")[:160] if r.details else ""
        lines.append(f"| {icon} | `{r.name}` | {r.source} | {r.passed_runs}/{r.total_runs} | {detail} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--repeat", type=int, default=int(os.environ.get("EVAL_REPEAT", 3)))
    parser.add_argument("--cases", help="comma-separated case names to run (default: all)")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--markdown", type=Path, help="write a markdown results table here")
    parser.add_argument("--json", type=Path, help="write machine-readable results here")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--expect-fail", action="store_true", help="succeed only if every selected case fails")
    args = parser.parse_args()

    # LLMJudge evaluators read ANTHROPIC_API_KEY; in CI the key is passed as AGENT_ANTHROPIC_API_KEY
    # (see app/config.py), so expose it to this process only.
    if config.anthropic_api_key():
        os.environ.setdefault("ANTHROPIC_API_KEY", config.anthropic_api_key())

    dataset = load_dataset(args.dataset)
    if args.cases:
        wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
        unknown = wanted - {c.name for c in dataset.cases}
        if unknown:
            print(f"Unknown case(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        dataset.cases = [c for c in dataset.cases if c.name in wanted]

    report = dataset.evaluate_sync(task, repeat=args.repeat, max_concurrency=args.concurrency, progress=False)
    results = summarise(dataset, report)
    markdown = to_markdown(results, args.repeat)
    print(markdown)
    for r in results:
        for d in dict.fromkeys(r.details):  # unique, in order
            print(f"  {r.name}: {d}")

    if args.markdown:
        args.markdown.write_text(markdown + "\n")
    if args.json:
        args.json.write_text(json.dumps([asdict(r) | {"passed": r.passed} for r in results], indent=2))

    if args.expect_fail:
        return 0 if all(not r.passed for r in results) else 1
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
