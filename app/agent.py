"""The Grindstone data assistant: a Pydantic AI agent that answers business questions with SQL.

This file, `app/prompts/system.md` and `app/tools.py` are what the optimisation loop is allowed to change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ToolCallPart, ToolReturnPart
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.settings import ModelSettings

from app import config, tools


class AgentAnswer(BaseModel):
    """The structured answer returned to the user."""

    answer: str = Field(description="Short answer for the user, in plain English.")
    value: float | None = Field(
        default=None,
        description="The single headline number, if the question asks for one (a count, total, average...). "
        "Money must be in pounds, not pence. Null if there is no single number.",
    )
    status: Literal["answered", "declined", "needs_clarification"] = Field(
        description="'answered' if you answered from the data, 'declined' if the request is out of scope or "
        "not allowed, 'needs_clarification' if you need the user to clarify before you can answer."
    )


@dataclass
class Deps:
    db_path: Path = config.DB_PATH
    today: date = config.TODAY


agent = Agent(
    deps_type=Deps,
    output_type=AgentAnswer,
    instructions=config.PROMPT_PATH.read_text(),
    model_settings=ModelSettings(temperature=0.0),
    retries=2,
)


@agent.instructions
def context(ctx: RunContext[Deps]) -> str:
    return (
        f"Today's date is {ctx.deps.today.isoformat()}.\n\n"
        f"Database schema:\n```sql\n{tools.describe_schema(ctx.deps.db_path)}\n```"
    )


@agent.tool
def run_sql(ctx: RunContext[Deps], query: str) -> str:
    """Run a read-only SQL query (SQLite dialect) against the company database and return the rows."""
    return tools.run_sql(ctx.deps.db_path, query)


def build_model() -> Model:
    if config.AGENT_MODEL == "test":  # offline mode for UI/plumbing checks: calls tools with dummy args, no API key
        from pydantic_ai.models.test import TestModel

        return TestModel(call_tools=["run_sql"])
    return AnthropicModel(config.AGENT_MODEL, provider=AnthropicProvider(api_key=config.anthropic_api_key(), base_url=config.ANTHROPIC_BASE_URL))


@dataclass
class ToolStep:
    tool: str
    args: dict
    result: str


@dataclass
class AgentRun:
    question: str
    output: AgentAnswer
    steps: list[ToolStep] = field(default_factory=list)


def extract_steps(messages: list[ModelMessage]) -> list[ToolStep]:
    """Pair each tool call with its result, for the trace shown in the UI and in feedback issues."""
    calls: dict[str, ToolCallPart] = {}
    steps: list[ToolStep] = []
    for message in messages:
        for part in message.parts:
            if isinstance(part, ToolCallPart) and part.tool_name != "final_result":
                calls[part.tool_call_id] = part
            elif isinstance(part, ToolReturnPart) and part.tool_call_id in calls:
                call = calls[part.tool_call_id]
                args = call.args if isinstance(call.args, dict) else json.loads(call.args or "{}")
                steps.append(ToolStep(tool=call.tool_name, args=args, result=str(part.content)))
    return steps


async def ask(question: str, deps: Deps | None = None, model: Model | None = None) -> AgentRun:
    result = await agent.run(question, deps=deps or Deps(), model=model or build_model())
    return AgentRun(question=question, output=result.output, steps=extract_steps(result.all_messages()))


if __name__ == "__main__":
    import asyncio
    import sys

    run = asyncio.run(ask(" ".join(sys.argv[1:]) or "How many orders did we get last month?"))
    for step in run.steps:
        print(f"-- {step.tool}: {step.args}\n{step.result}\n")
    print(run.output.model_dump_json(indent=2))
