# Multi-Agent Research & Evidence Assistant

LangGraph pipeline of five agents (Planner → Research → Verification → Writer → Review) using Anthropic (LLM), Tavily (web search), Streamlit UI, SQLite history, pytest.

**Evidence rules:** sources are only cited if their text was retrieved. A claim is "verified" only if its quote appears verbatim in the retrieved source AND an LLM entailment check says the quote supports the claim. The writer sees only verified claims. Missing keys or API failures stop the run with a clear error; no dummy data is ever used.

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # then edit .env: GROQ_API_KEY, TAVILY_API_KEY
```

Keys: https://console.anthropic.com and https://app.tavily.com

## Run / test

```powershell
streamlit run app.py
pytest -q
```

## GitHub

```powershell
git init; git add .; git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

`.env` and `*.db` are git-ignored.

## Deploy (Streamlit Community Cloud)

Push to GitHub → share.streamlit.io → New app → select repo, main file `app.py` → Advanced settings → Secrets:

```toml
GROQ_API_KEY = "..."
TAVILY_API_KEY = "..."
```

Note: SQLite on Community Cloud is ephemeral (history resets on restart); use a VM/container with a mounted volume for durable history.

## Known limits

Verification checks quote presence plus LLM entailment; it is not proof of truth. Quality review is partly LLM-based.
