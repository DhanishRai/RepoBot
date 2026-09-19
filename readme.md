# GitBot Studio

GitBot Studio turns a public GitHub repository into an interactive intelligence dashboard. It collects repository metadata, README content, configuration files, CI workflows, and the first entries in the Git tree, then uses Gemini to explain the project in plain English.

## Features

- Repository metadata, stars, language, README, dependencies, and file tree inspection
- Blueprint with a plain-English summary, local runbook, and CI/CD explanation
- Grounded chat assistant that answers from the fetched repository context
- In-memory caching to avoid repeated GitHub API requests during a session
- Responsive Tokyo Night dashboard built with FastAPI, Tailwind CSS, and Markdown

## Requirements

- Python 3.10 or newer
- A public GitHub repository URL
- A Gemini API key for AI-generated blueprints and chat

## Setup

From the project directory:

```bash
cd gitbot-studio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and set your Gemini key:

```env
GEMINI_API_KEY=your_gemini_api_key
GITHUB_TOKEN=
```

`GITHUB_TOKEN` is optional, but it increases the GitHub API rate limit for repository inspection. Keep `.env` private and never commit API keys.

## Run

```bash
uvicorn main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser, enter a public GitHub URL, and select **Analyze**. After analysis, ask questions about the repository in the assistant panel.

Without `GEMINI_API_KEY`, the application can still start and inspect repositories, but it uses a basic local blueprint fallback and cannot provide live AI chat answers.

## API Endpoints

### `POST /api/inspect`

Inspect and cache a repository:

```json
{
	"repo_url": "https://github.com/owner/repository"
}
```

Returns the generated blueprint and repository statistics.

### `POST /api/chat`

Ask a question about a repository that has already been inspected:

```json
{
	"repo_url": "https://github.com/owner/repository",
	"question": "How do I run the tests?",
	"history": []
}
```

## Project Structure

```text
gitbot-studio/
├── .env.example
├── requirements.txt
├── github_service.py  # GitHub API and repository inspection
├── ai_service.py      # Gemini prompts and grounded responses
├── main.py            # FastAPI application and API routes
└── static/
		├── index.html     # Dashboard layout
		└── app.js         # Browser state and API interactions
```
