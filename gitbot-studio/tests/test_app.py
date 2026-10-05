from fastapi.testclient import TestClient

import main
from github_service import parse_repo_url


client = TestClient(main.app)


def setup_function():
    main.REPO_CACHE.clear()


def test_parse_repository_url_variants():
    assert parse_repo_url("https://github.com/fastapi/fastapi") == ("fastapi", "fastapi")
    assert parse_repo_url("github.com/fastapi/fastapi.git") == ("fastapi", "fastapi")
    assert parse_repo_url("https://github.com/fastapi/fastapi/tree/master/docs") == ("fastapi", "fastapi")


def test_parse_repository_url_rejects_non_github_and_invalid_names():
    for value in (
        "https://github.com.example.com/owner/repo",
        "https://user@github.com/owner/repo",
        "https://github.com/owner/repo/../../other",
        "https://github.com/owner/repo name",
    ):
        try:
            parse_repo_url(value)
        except ValueError:
            continue
        raise AssertionError(f"Expected invalid repository URL to fail: {value}")


def test_health_reports_application_available():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "gemini_configured" in response.json()


def test_inspect_caches_repository(monkeypatch):
    data = {
        "repository": {"name": "owner/repo", "stars": 2},
        "tree": [{"path": "README.md", "type": "blob"}],
        "tree_truncated": False,
    }
    calls = []
    monkeypatch.setattr(main, "inspect_repository", lambda url: calls.append(url) or data)
    monkeypatch.setattr(main, "generate_blueprint", lambda value: "## Summary\nDemo")

    first = client.post("/api/inspect", json={"repo_url": "https://github.com/owner/repo"})
    second = client.post("/api/inspect", json={"repo_url": "https://github.com/owner/repo"})

    assert first.status_code == 200
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert len(calls) == 1
    assert second.json()["tree"][0]["path"] == "README.md"


def test_inspect_rejects_invalid_repository_url():
    response = client.post("/api/inspect", json={"repo_url": "https://example.com/owner/repo"})
    assert response.status_code == 400


def test_chat_requires_repository_inspection_first():
    response = client.post(
        "/api/chat",
        json={"repo_url": "https://github.com/owner/repo", "question": "How do I test it?"},
    )
    assert response.status_code == 409