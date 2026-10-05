# GitBot Studio

GitBot Studio is a small FastAPI web application that inspects a **public GitHub repository** and presents a plain-English project blueprint, repository file list, and context-aware Gemini chat. It collects repository metadata, a README, common dependency/build manifests, and selected GitHub Actions workflows.

## Requirements

- Python 3.10 or newer
- Git (for cloning repositories from the generated runbook)
- Internet access to the GitHub API and the frontend CDN services
- A Gemini API key for AI-generated blueprints and live chat (optional; repository inspection and a basic fallback blueprint work without it)
- A GitHub personal access token is optional, but recommended to increase the unauthenticated API rate limit

## Quick start

Run these commands from the repository root:

```bash
cd gitbot-studio
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1` instead. Edit `gitbot-studio/.env` and add keys as needed:

```dotenv
GEMINI_API_KEY=your_gemini_api_key
GITHUB_TOKEN=your_github_token_optional
```

Keep `.env` private. It is excluded from Git by `.gitignore`; never paste credentials into source files, screenshots, or issue reports. If you do not need live AI, leave `GEMINI_API_KEY` empty. To use the full assistant, create a Gemini API key in Google AI Studio. A GitHub token can be a fine-grained token with public repository read access; do not grant write access for this app.

Start the development server while the virtual environment is active:

```bash
uvicorn main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000), enter a public GitHub repository URL, and select **Analyze**. Ask questions after inspection. Stop the server with `Ctrl+C`.

Confirm the server is healthy at [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health). Interactive API documentation is at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Tests

Install development/test dependencies and run the automated checks from `gitbot-studio/`:

```bash
pip install -r requirements-dev.txt
pytest -q
```

## API

- `GET /api/health` — app status and whether Gemini is configured.
- `POST /api/inspect` — accepts `{"repo_url":"https://github.com/owner/repository"}` and returns repository statistics, a generated/fallback blueprint, and up to 45 file-tree entries.
- `POST /api/chat` — accepts `repo_url`, a `question`, and optional recent `history`. Inspect the repository first. The in-memory result cache expires after 15 minutes and is limited to 64 repositories per process.

## Project layout

```text
gitbot-studio/
├── .env.example
├── .gitignore
├── requirements.txt
├── requirements-dev.txt
├── main.py                 # FastAPI routes and bounded in-memory cache
├── github_service.py       # GitHub API and repository context collection
├── ai_service.py           # Gemini prompts and non-AI fallback blueprint
├── static/
│   ├── index.html           # Dashboard
│   └── app.js               # Browser UI and API calls
└── tests/
    └── test_app.py
```

## Troubleshooting

- **`ModuleNotFoundError`**: activate `.venv` and install `requirements.txt` again.
- **GitHub rate limit**: configure `GITHUB_TOKEN` and retry after the rate limit resets.
- **Repository not found**: check the spelling and make sure the repository is public. Private repositories are not supported.
- **No AI answers**: check `GEMINI_API_KEY` in `.env`, restart Uvicorn after editing it, and verify the key/model is enabled for your account. Without a key, inspect still works, but chat returns a configuration message.
- **Styles or Markdown library missing**: the current UI loads Tailwind CSS, Marked, and DOMPurify from CDNs, so the browser needs internet access. The Python backend itself does not depend on those CDNs.
- **Port 8000 is already used**: start Uvicorn with `--port 8001` and open `http://127.0.0.1:8001`.

## Before public deployment

This is a local development app, not a production-hardened multi-user service. Before exposing it to the internet, add authentication and per-user rate limiting, move the cache to a shared store if using multiple workers, configure HTTPS and a restrictive host/origin policy, set request and AI spending limits, pin and self-host frontend assets, and deploy behind a production ASGI server/reverse proxy. Do not run Uvicorn with `--reload` in production.
