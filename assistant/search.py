import os
import requests
from bs4 import BeautifulSoup
from .llm import ConfigError, ServiceError

UA = {"User-Agent": "Mozilla/5.0 (ResearchAssistant)"}


def web_search(query, n=4):
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise ConfigError("TAVILY_API_KEY is not set")
    try:
        r = requests.post("https://api.tavily.com/search", timeout=30,
                          headers={"Authorization": f"Bearer {key}"},
                          json={"query": query, "max_results": n, "include_raw_content": True})
        r.raise_for_status()
    except requests.RequestException as e:
        raise ServiceError(f"Search API error: {e}") from e
    return [{"url": x["url"], "title": x.get("title") or x["url"],
             "content": x.get("raw_content") or ""} for x in r.json().get("results", []) if x.get("url")]


def fetch_page(url):
    r = requests.get(url, timeout=15, headers=UA)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for t in soup(["script", "style", "nav", "footer", "header"]):
        t.decompose()
    return " ".join(soup.get_text(" ").split())
