"""FastAPI application for GitBot Studio."""

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai_service import ask_repo_question, generate_blueprint
from github_service import inspect_repository, parse_repo_url

BASE_DIR = Path(__file__).resolve().parent
REPO_CACHE: dict[str, dict[str, Any]] = {}

app = FastAPI(title="GitBot Studio", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class InspectRequest(BaseModel):
    repo_url: str = Field(min_length=1)


class ChatRequest(BaseModel):
    repo_url: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=4000)
    history: list[dict[str, Any]] = Field(default_factory=list)


def _cache_key(repo_url: str) -> str:
    owner, repo = parse_repo_url(repo_url)
    return f"{owner.lower()}/{repo.lower()}"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.post("/api/inspect")
def inspect(request: InspectRequest) -> dict[str, Any]:
    try:
        key = _cache_key(request.repo_url)
        if key not in REPO_CACHE:
            data = inspect_repository(request.repo_url)
            REPO_CACHE[key] = {"data": data, "blueprint": generate_blueprint(data)}
        cached = REPO_CACHE[key]
        repo = cached["data"]["repository"]
        return {"blueprint": cached["blueprint"], "stats": repo, "cached": key in REPO_CACHE}
    except (ValueError, ConnectionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Repository inspection failed: {exc}") from exc


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, str]:
    try:
        key = _cache_key(request.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    cached = REPO_CACHE.get(key)
    if not cached:
        raise HTTPException(status_code=409, detail="Analyze this repository before starting a chat.")
    try:
        answer = ask_repo_question(cached["data"], request.history, request.question)
        return {"answer": answer}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chat request failed: {exc}") from exc