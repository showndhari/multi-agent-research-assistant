import pytest
from assistant import agents, db, graph, llm, search

TEXT = "The Eiffel Tower was completed in 1889 for the World's Fair in Paris. " * 6


def test_quote_verification():
    assert agents.quote_in_source("completed in 1889 for the World's Fair", TEXT)
    assert not agents.quote_in_source("completed in 1999 for the World's Fair", TEXT)
    assert not agents.quote_in_source("short", "short")


def test_citation_mapping_and_invalid():
    src = [{"id": 1, "url": "https://a.com/x", "title": "A"}]
    out = agents.render_citations("Fact [1]. Bad [7].", src)
    assert "[1](https://a.com/x)" in out and "[7]" in out and "[7](" not in out
    assert "## References" in out and "1. [A](https://a.com/x)" in out


def test_missing_keys(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(llm.ConfigError):
        llm.complete("s", "u")
    with pytest.raises(llm.ConfigError):
        search.web_search("q")


def test_db_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    rid = db.save_run({"question": "q", "report": "r", "sources": [{"id": 1}]})
    assert db.list_runs()[0]["id"] == rid and db.get_run(rid)["state"]["sources"] == [{"id": 1}]


def test_failure_stops_pipeline(monkeypatch):
    def boom(*a, **k):
        raise llm.ServiceError("down")
    monkeypatch.setattr(llm, "complete_json", boom)
    s = graph.build().invoke({"question": "q"})
    assert "Planner agent failed" in s["error"]
    assert s["statuses"]["Planner"]["status"] == "failed" and "Research" not in s["statuses"]


# MOCKED wiring test: fakes are used ONLY here to test orchestration, never in the app.
def test_graph_wiring_with_fakes(monkeypatch):
    def fake_json(system, user, max_tokens=0):
        s = system.lower()
        if "planner" in s:
            return {"subtasks": [{"task": "t", "queries": ["a", "b"]}]}
        if "extractor" in s:
            return {"claims": [{"claim": "Tower finished 1889", "quote": "completed in 1889 for the World's Fair"},
                               {"claim": "Fabricated", "quote": "this quote does not exist in the text at all"}]}
        if "judge" in s:
            return {"results": [{"i": 0, "supported": True}]}
        return {"issues": [], "score": 9, "summary": "ok"}
    monkeypatch.setattr(llm, "complete_json", fake_json)
    monkeypatch.setattr(llm, "complete", lambda *a, **k: "# Report\n\nThe tower was finished in 1889 as described in the source material [1].")
    monkeypatch.setattr(search, "web_search", lambda q: [{"url": "https://e.com/p", "title": "E", "content": TEXT}])
    s = graph.build().invoke({"question": "q"})
    assert not s.get("error"), s
    assert [c["status"] for c in s["claims"]] == ["verified", "unsupported"]
    assert "(https://e.com/p)" in s["report"] and s["review"]["passed"]
    assert all(v["status"] == "completed" for v in s["statuses"].values()) and len(s["statuses"]) == 5
