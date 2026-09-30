"""Custom evaluators for the Grindstone data assistant.

Prefer these deterministic checks. Use the built-in `LLMJudge` only when the expected behaviour
can't be pinned to a number, a phrase or a status.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext

from app.agent import AgentAnswer


class EvalInput(BaseModel):
    question: str


@dataclass
class NumericMatch(Evaluator[EvalInput, AgentAnswer]):
    """The headline `value` must equal `expected` (within `tolerance`)."""

    expected: float
    tolerance: float = 0.5

    def evaluate(self, ctx: EvaluatorContext[EvalInput, AgentAnswer]) -> EvaluationReason:
        got = ctx.output.value
        ok = got is not None and abs(got - self.expected) <= self.tolerance
        return EvaluationReason(value=ok, reason=f"value={got}, expected {self.expected} ± {self.tolerance}")


@dataclass
class AnswerContains(Evaluator[EvalInput, AgentAnswer]):
    """The prose `answer` must mention at least one of `any_of` (case-insensitive)."""

    any_of: list[str] = field(default_factory=list)

    def evaluate(self, ctx: EvaluatorContext[EvalInput, AgentAnswer]) -> EvaluationReason:
        text = ctx.output.answer.lower()
        ok = any(s.lower() in text for s in self.any_of)
        return EvaluationReason(value=ok, reason=f"looked for any of {self.any_of} in: {ctx.output.answer!r}")


@dataclass
class StatusIs(Evaluator[EvalInput, AgentAnswer]):
    """The answer `status` must be `expected` (answered | declined | needs_clarification)."""

    expected: str

    def evaluate(self, ctx: EvaluatorContext[EvalInput, AgentAnswer]) -> EvaluationReason:
        got = ctx.output.status
        return EvaluationReason(value=got == self.expected, reason=f"status={got}, expected {self.expected}")


CUSTOM_EVALUATORS = [NumericMatch, AnswerContains, StatusIs]
