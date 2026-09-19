"""Gemini prompts for repository blueprints and grounded chat."""

import json
import os
from typing import Any

from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL = "gemini-2.5-flash"
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _context(repo_data: dict[str, Any]) -> str:
    return json.dumps(repo_data, ensure_ascii=True, indent=2)[:90000]


def _fallback_blueprint(repo_data: dict[str, Any]) -> str:
    repo = repo_data["repository"]
    configs = ", ".join(repo_data.get("configuration_files", {})) or "the repository files"
    return (f"## Plain-English Summary\n{repo['name']} is a public software project. {repo['description']}\n\n"
            f"## Local Quick-Start Runbook\n```bash\ngit clone {repo['url']}\ncd {repo['name'].split('/')[-1]}\n# Install dependencies described by: {configs}\n```\n\n"
            "## CI/CD & Automation Breakdown\nNo Gemini API key is configured, so workflow details are available in the repository context but could not be summarized.")


def generate_blueprint(repo_data: dict[str, Any]) -> str:
    """Generate the three-section repository blueprint in Markdown."""
    if not os.getenv("GEMINI_API_KEY", "").strip():
        return _fallback_blueprint(repo_data)
    prompt = f"""You are GitBot Studio. Analyze only this fetched GitHub context:
{_context(repo_data)}

Return exactly three Markdown sections with these headings:
## Plain-English Summary
Write 2-3 sentences for non-technical users.
## Local Quick-Start Runbook
Give exact OS-agnostic terminal commands to clone, install dependencies, and run this project. Only state commands supported by the context; call out missing information plainly.
## CI/CD & Automation Breakdown
Explain in plain English what tests, builds, releases, or deployments the workflow YAML files trigger on push.
"""
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return response.text or _fallback_blueprint(repo_data)


def ask_repo_question(repo_data: dict[str, Any], chat_history: list[dict[str, Any]], question: str) -> str:
    """Answer a question strictly from the collected repository context."""
    if not os.getenv("GEMINI_API_KEY", "").strip():
        return "Gemini is not configured. Add GEMINI_API_KEY to .env to ask repository questions."
    history = json.dumps(chat_history[-10:], ensure_ascii=True)
    prompt = f"""You are a concise repository assistant. Answer strictly from the repository context below.
If the context does not contain the answer, say that clearly and do not invent details.
Context:
{_context(repo_data)}
Recent chat:
{history}
Question: {question}
Use short paragraphs or bullets and Markdown when useful."""
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return response.text or "I could not find an answer in the fetched repository context."