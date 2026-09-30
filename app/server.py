"""Minimal web app: ask the data assistant a question, then give 👍/👎 feedback on the answer.

    uv run uvicorn app.server:app --reload
"""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import config, feedback
from app.agent import ask

app = FastAPI(title="Grindstone data assistant")


class AskRequest(BaseModel):
    question: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse(config.ROOT / "app" / "static" / "index.html")


@app.get("/api/config")
def get_config() -> dict:
    return {"model": config.AGENT_MODEL, "github_repo": os.environ.get("GITHUB_REPOSITORY") if os.environ.get("GITHUB_TOKEN") else None}


@app.post("/api/ask")
async def api_ask(req: AskRequest) -> dict:
    result = await ask(req.question)
    run = {
        "id": uuid.uuid4().hex[:10],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "question": req.question,
        "output": result.output.model_dump(),
        "steps": [asdict(s) for s in result.steps],
        "model": config.AGENT_MODEL,
        "app_commit": feedback.app_commit(),
    }
    feedback.save_run(run)
    return run


@app.post("/api/feedback")
def api_feedback(fb: feedback.Feedback) -> dict:
    run = feedback.load_run(fb.run_id)
    if run is None:
        raise HTTPException(404, "unknown run")
    if not fb.what_was_wrong.strip():
        raise HTTPException(422, "please say what was wrong")
    return feedback.create_issue(run, fb)
