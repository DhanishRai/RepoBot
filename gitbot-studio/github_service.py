"""GitHub REST API access and repository context collection."""

import os
import re
from typing import Any
from urllib.parse import quote, unquote, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

API_ROOT = "https://api.github.com"
REQUEST_TIMEOUT = 15
MAX_WORKFLOWS = 8
MAX_FILE_CHARS = 20000


def _headers(*, include_token: bool = True) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GitBot-Studio"}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token and include_token:
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
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        raise ValueError("Please provide a valid GitHub repository URL.")
    if (parsed.hostname or "").lower() not in {"github.com", "www.github.com"}:
        raise ValueError("Please provide a URL hosted on github.com.")
    if parsed.port not in {None, 80, 443}:
        raise ValueError("Please provide a GitHub URL without a custom port.")
    parts = [part for part in parsed.path.split("/") if part]
    if any(unquote(part) in {".", ".."} for part in parts):
        raise ValueError("The repository URL is not valid.")
    if len(parts) < 2:
        raise ValueError("The URL must include both an owner and repository name.")
    owner, repo = parts[0], parts[1]
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if (not re.fullmatch(r"[A-Za-z0-9-]+", owner)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo)
            or repo in {".", ".."}):
        raise ValueError("The repository URL is not valid.")
    return owner, repo


def _request_json(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(
        f"{API_ROOT}{endpoint}", headers=_headers(), params=params, timeout=REQUEST_TIMEOUT
    )
    if response.status_code == 404:
        return None
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        raise ConnectionError("GitHub API rate limit reached. Add a GITHUB_TOKEN to your .env file and try again later.")
    response.raise_for_status()
    return response.json()


def fetch_file_content(owner: str, repo: str, path: str, branch: str | None = None) -> str | None:
    """Fetch a text file from the selected branch without trying unrelated branches."""
    if not branch:
        return None
    encoded_path = quote(path.lstrip("/"), safe="/")
    raw_url = (f"https://raw.githubusercontent.com/{quote(owner)}/{quote(repo)}/"
               f"{quote(branch, safe='/')}/{encoded_path}")
    response = requests.get(raw_url, headers=_headers(include_token=False), timeout=REQUEST_TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.text


def _find_readme(owner: str, repo: str, branch: str) -> str | None:
    for filename in ("README.md", "README.rst", "README", "readme.md"):
        content = fetch_file_content(owner, repo, filename, branch)
        if content is not None:
            return content[:MAX_FILE_CHARS]
    return None


def inspect_repository(repo_url: str) -> dict[str, Any]:
    """Collect the repository context needed by the dashboard and AI assistant."""
    owner, repo = parse_repo_url(repo_url)
    metadata = _request_json(f"/repos/{owner}/{repo}")
    if not metadata:
        raise ValueError("Repository not found or not publicly accessible.")
    branch = metadata.get("default_branch") or "main"

    encoded_branch = quote(branch, safe="")
    tree_response = _request_json(
        f"/repos/{quote(owner)}/{quote(repo)}/git/trees/{encoded_branch}", params={"recursive": "1"}
    ) or {}
    tree = tree_response.get("tree", [])
    tree_items = [
        {"path": item.get("path", ""), "type": item.get("type", "")}
        for item in tree[:45]
        if item.get("path")
    ]

    configuration_files: dict[str, str] = {}
    config_names = (
        "package.json", "requirements.txt", "pyproject.toml", "Pipfile",
        "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts",
        "Gemfile", "composer.json", "Dockerfile", "docker-compose.yml",
        "Makefile", "justfile",
    )
    root_files = {item.get("path", "") for item in tree if item.get("type") == "blob"}
    for filename in config_names:
        if filename not in root_files:
            continue
        content = fetch_file_content(owner, repo, filename, branch)
        if content is not None:
            configuration_files[filename] = content[:MAX_FILE_CHARS]

    workflows: dict[str, str] = {}
    workflow_paths = []
    for item in tree:
        path = item.get("path", "")
        if item.get("type") == "blob" and path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml")):
            workflow_paths.append(path)
    for path in workflow_paths[:MAX_WORKFLOWS]:
        content = fetch_file_content(owner, repo, path, branch)
        if content is not None:
            workflows[path] = content[:MAX_FILE_CHARS]

    return {
        "repository": {
            "name": metadata.get("full_name", f"{owner}/{repo}"),
            "url": metadata.get("html_url", repo_url),
            "description": metadata.get("description") or "No description provided.",
            "stars": metadata.get("stargazers_count", 0),
            "forks": metadata.get("forks_count", 0),
            "language": metadata.get("language") or "Not detected",
            "default_branch": branch,
            "updated_at": metadata.get("updated_at"),
            "topics": metadata.get("topics", []),
        },
        "readme": _find_readme(owner, repo, branch) or "No README file was found.",
        "configuration_files": configuration_files,
        "workflows": workflows,
        "tree": tree_items,
        "tree_truncated": bool(tree_response.get("truncated")) or len(tree) > len(tree_items),
        "workflow_count": len(workflow_paths),
    }