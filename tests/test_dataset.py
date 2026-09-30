"""Sanity checks on the eval dataset itself (no LLM calls).

Every case with metadata.reference_sql must agree with its expected value, so an eval written from
feedback can't silently encode a wrong "correct answer".
"""

import sqlite3

import pytest

from app import config
from evals.evaluators import AnswerContains, NumericMatch
from evals.run import load_dataset

DATASET = load_dataset()


def test_case_names_are_unique():
    names = [c.name for c in DATASET.cases]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("case", [c for c in DATASET.cases if (c.metadata or {}).get("reference_sql")], ids=lambda c: c.name)
def test_reference_sql_matches_expectation(case):
    with sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True) as conn:
        actual = conn.execute(case.metadata["reference_sql"]).fetchone()[0]
    checked = False
    for ev in case.evaluators:
        if isinstance(ev, NumericMatch):
            assert abs(float(actual) - ev.expected) <= ev.tolerance, f"reference_sql gives {actual}, case expects {ev.expected}"
            checked = True
        if isinstance(ev, AnswerContains):
            assert any(s.lower() in str(actual).lower() or str(actual).lower() in s.lower() for s in ev.any_of)
            checked = True
    assert checked, "reference_sql given but no NumericMatch/AnswerContains evaluator to check it against"
