"""FastAPI application for GitBot Studio."""

from pathlib import Path
import logging
import os
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai_service import ask_repo_question, generate_blueprint
from github_service import inspect_repository, parse_repo_url

BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)
CACHE_TTL_SECONDS = 15 * 60
CACHE_MAX_ENTRIES = 64
REPO_CACHE: dict[str, dict[str, Any]] = {}

app = FastAPI(title="GitBot Studio", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class InspectRequest(BaseModel):
    repo_url: str = Field(min_length=1)


class ChatRequest(BaseModel):
    repo_url: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=4000)
    history: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


def _cache_key(repo_url: str) -> str:
    owner, repo = parse_repo_url(repo_url)
    return f"{owner.lower()}/{repo.lower()}"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    """Report application and optional AI configuration status."""
    return {"status": "ok", "gemini_configured": bool(os.getenv("GEMINI_API_KEY", "").strip())}


def _cached(key: str) -> dict[str, Any] | None:
    entry = REPO_CACHE.get(key)
    if not entry:
        return None
    if time.monotonic() - entry["created_at"] >= CACHE_TTL_SECONDS:
        REPO_CACHE.pop(key, None)
        return None
    return entry


@app.post("/api/inspect")
def inspect(request: InspectRequest) -> dict[str, Any]:
    try:
        key = _cache_key(request.repo_url)
        cached = _cached(key)
        was_cached = cached is not None
        if not cached:
            data = inspect_repository(request.repo_url)
            cached = {"data": data, "blueprint": generate_blueprint(data), "created_at": time.monotonic()}
            if len(REPO_CACHE) >= CACHE_MAX_ENTRIES:
                oldest = min(REPO_CACHE, key=lambda item: REPO_CACHE[item]["created_at"])
                REPO_CACHE.pop(oldest, None)
            REPO_CACHE[key] = cached
        repo = cached["data"]["repository"]
        return {
            "blueprint": cached["blueprint"],
            "stats": repo,
            "tree": cached["data"]["tree"],
            "tree_truncated": cached["data"]["tree_truncated"],
            "cached": was_cached,
        }
    except (ValueError, ConnectionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Repository inspection failed")
        raise HTTPException(status_code=502, detail="Repository inspection failed. Check the repository URL and service connectivity.") from exc


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, str]:
    try:
        key = _cache_key(request.repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    cached = _cached(key)
    if not cached:
        raise HTTPException(status_code=409, detail="Analyze this repository before starting a chat.")
    try:
        answer = ask_repo_question(cached["data"], request.history, request.question)
        return {"answer": answer}
    except Exception as exc:
        logger.exception("Repository chat failed")
        raise HTTPException(status_code=502, detail="Chat request failed. Please try again.") from exc