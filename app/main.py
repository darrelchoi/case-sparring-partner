"""FastAPI server: serves the web app and the JSON API. Every agent call goes through the orchestrator."""

from __future__ import annotations

import json
import random
import re

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import config, guards, history, orchestrator
from app.agents.generator import generate_case
from app.cases import all_cases, library
from app.usage import PRICES, spent_today

app = FastAPI(title="Case Sparring Partner")
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.middleware("http")
async def no_stale_pages(request: Request, call_next):
    """Make browsers re-check the page and its CSS/JS every time, so an update is never hidden behind an old cached copy."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.exception_handler(guards.Blocked)
async def blocked(_: Request, e: guards.Blocked):
    return JSONResponse({"error": str(e), "blocked": True}, status_code=400)


@app.exception_handler(KeyError)
async def missing(_: Request, e: KeyError):
    return JSONResponse({"error": str(e).strip("'\"")}, status_code=404)


@app.exception_handler(RuntimeError)
async def runtime(_: Request, e: RuntimeError):
    return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/")
def index():
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/api/config")
def get_config():
    return {
        "model": config.MODEL_NAME, "prices_per_1m": PRICES,
        "limits": {"max_input_chars": config.MAX_INPUT_CHARS, "max_turns": config.MAX_TURNS_PER_CASE,
                   "max_cost_per_case": config.MAX_COST_PER_CASE, "max_cost_per_day": config.MAX_COST_PER_DAY},
        "spent_today": round(spent_today(), 6),
    }


@app.get("/api/cases")
def list_cases():
    lib = library()
    out = []
    for c in all_cases().values():
        out.append({"id": c.id, "title": c.title, "case_type": c.case_type, "industry": c.industry,
                    "difficulty": c.difficulty, "generated": c.id not in lib})
    return out


class StartReq(BaseModel):
    user: str = Field(max_length=40)
    case_id: str | None = None
    coach_pick: bool = False


@app.post("/api/start")
def start(req: StartReq):
    case_id = req.case_id
    reason = None
    if req.coach_pick or not case_id:
        past = history.get(req.user)
        lib = library()
        if past and past[-1].get("coach_next_case_id") in lib:
            case_id = past[-1]["coach_next_case_id"]
            reason = f"Your coach picked this to work on {past[-1].get('focus', 'your weakest area')}."
        else:
            easy = [c.id for c in lib.values() if c.difficulty == 1]
            case_id = random.choice(easy)
            reason = "No history yet, so here's a good first case."
    s = orchestrator.start_case(req.user, case_id)
    return {"opening": s.case.prompt, "reason": reason, "state": s.public_state()}


class TurnReq(BaseModel):
    session_id: str
    text: str = Field(max_length=5_000)  # the guard enforces the real (lower) limit with a friendly message


@app.post("/api/turn")
async def turn(req: TurnReq):
    return await orchestrator.candidate_turn(req.session_id, req.text)


class EndReq(BaseModel):
    session_id: str


@app.post("/api/end")
async def end(req: EndReq):
    return await orchestrator.end_case(req.session_id)


class GenReq(BaseModel):
    case_type: str
    industry: str = Field(max_length=60)
    difficulty: int = 2


@app.post("/api/generate")
async def generate(req: GenReq):
    if spent_today() >= config.MAX_COST_PER_DAY:
        raise guards.Blocked("The app has reached today's spending cap. Please try again tomorrow.")
    res = await generate_case(req.case_type, req.industry, req.difficulty)
    case = res["case"]
    return {"ok": res["ok"], "attempts": res["attempts"], "usage": res["usage"],
            "case": {"id": case.id, "title": case.title, "case_type": case.case_type, "industry": case.industry,
                     "difficulty": case.difficulty} if case else None}


@app.get("/api/run/{session_id}")
def get_run(session_id: str):
    """A finished case, for the review screen: transcript, exhibits that were unlocked, scorecard, coach plan."""
    sid = re.sub(r"[^a-f0-9]", "", session_id)[:12]
    files = sorted(config.RUNS_DIR.glob(f"*_{sid}.json")) if sid else []
    if not files:
        raise KeyError("No saved case with that id.")
    run = json.loads(files[-1].read_text())
    cases = all_cases()
    case = cases.get(run["case_id"])
    nxt = cases.get(run["coach"]["next_case_id"])
    run["case"] = {"title": case.title, "case_type": case.case_type, "industry": case.industry} if case else None
    run["exhibits"] = [ex.model_dump() for ex in case.exhibits if ex.unlock_topic in run["revealed"]] if case else []
    run["next_case"] = {"id": nxt.id, "title": nxt.title} if nxt else None
    return run


@app.get("/api/history")
def get_history(user: str):
    return history.get(user)


@app.delete("/api/history")
def delete_history(user: str):
    return {"deleted": history.delete(user)}
