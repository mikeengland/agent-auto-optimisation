"""Exercise the agent wiring with Pydantic AI's TestModel (no API key needed)."""

from pydantic_ai.models.test import TestModel

from app.agent import ask


async def test_agent_runs_tool_and_returns_structured_answer():
    model = TestModel(call_tools=["run_sql"], custom_output_args={"answer": "42 orders", "value": 42, "status": "answered"})
    run = await ask("How many orders?", model=model)
    assert run.output.value == 42
    assert run.steps and run.steps[0].tool == "run_sql"
