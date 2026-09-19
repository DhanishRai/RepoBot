"""GitHub REST API access and repository context collection."""

import base64
import os
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

API_ROOT = "https://api.github.com"
REQUEST_TIMEOUT = 20


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GitBot-Studio"}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def parse_repo_url(url: str) -> tuple[str, str]:
    """Extract an owner and repository name from a public GitHub URL."""
    candidate = (url or "").strip()
    if not candidate:
        raise ValueError("A GitHub repository URL is required.")
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError("Please provide a URL hosted on github.com.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("The URL must include both an owner and repository name.")
    owner, repo = parts[0], parts[1]
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo or any(value in {".", ".."} for value in (owner, repo)):
        raise ValueError("The repository URL is not valid.")
    return owner, repo


def _request_json(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(
        f"{API_ROOT}{endpoint}", headers=_headers(), params=params, timeout=REQUEST_TIMEOUT
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def fetch_file_content(owner: str, repo: str, path: str, branch: str | None = None) -> str | None:
    """Fetch a text file from raw GitHub, trying the default branch and common fallbacks."""
    branches = [branch, "main", "master"]
    seen: set[str] = set()
    for candidate in branches:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{candidate}/{path.lstrip('/')}"
        response = requests.get(raw_url, headers=_headers(), timeout=REQUEST_TIMEOUT)
        if response.ok:
            return response.text
    return None


def _decode_content(item: dict[str, Any]) -> str | None:
    encoded = item.get("content")
    if not encoded:
        return None
    try:
        return base64.b64decode(encoded.replace("\n", "")).decode("utf-8", errors="replace")
    except (ValueError, UnicodeDecodeError):
        return None


def _find_readme(owner: str, repo: str, branch: str) -> str | None:
    for filename in ("README.md", "readme.md", "Readme.md"):
        content = fetch_file_content(owner, repo, filename, branch)
        if content is not None:
            return content
    return None


def inspect_repository(repo_url: str) -> dict[str, Any]:
    """Collect the repository context needed by the dashboard and AI assistant."""
    owner, repo = parse_repo_url(repo_url)
    metadata = _request_json(f"/repos/{owner}/{repo}")
    if not metadata:
        raise ValueError("Repository not found or not publicly accessible.")
    branch = metadata.get("default_branch") or "main"

    tree_response = _request_json(
        f"/repos/{owner}/{repo}/git/trees/{branch}", params={"recursive": "1"}
    ) or {}
    tree = tree_response.get("tree", [])
    tree_items = [
        {"path": item.get("path", ""), "type": item.get("type", "")}
        for item in tree[:45]
        if item.get("path")
    ]

    configuration_files: dict[str, str] = {}
    for filename in ("package.json", "requirements.txt", "go.mod", "Cargo.toml", "Dockerfile"):
        content = fetch_file_content(owner, repo, filename, branch)
        if content is not None:
            configuration_files[filename] = content[:20000]

    workflows: dict[str, str] = {}
    for item in tree:
        path = item.get("path", "")
        if item.get("type") == "blob" and path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml")):
            content = fetch_file_content(owner, repo, path, branch)
            if content is not None:
                workflows[path] = content[:20000]

    return {
        "repository": {
            "name": metadata.get("full_name", f"{owner}/{repo}"),
            "url": metadata.get("html_url", repo_url),
            "description": metadata.get("description") or "No description provided.",
            "stars": metadata.get("stargazers_count", 0),
            "language": metadata.get("language") or "Not detected",
            "default_branch": branch,
        },
        "readme": _find_readme(owner, repo, branch) or "No README file was found.",
        "configuration_files": configuration_files,
        "workflows": workflows,
        "tree": tree_items,
    }