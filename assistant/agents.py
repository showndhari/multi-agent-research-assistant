import re
from . import llm, search
import requests

MAX_SOURCES = 8


def _norm(s):
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_in_source(quote, content):
    q = _norm(quote)
    return len(q) >= 20 and q in _norm(content)


def render_citations(md, sources):
    by_id = {s["id"]: s for s in sources}
    md = re.sub(r"\[(\d+)\](?!\()", lambda m: f"[{m.group(1)}]({by_id[int(m.group(1))]['url']})"
                if int(m.group(1)) in by_id else m.group(0), md)
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]\(http", md)})
    refs = "\n".join(f"{n}. [{by_id[n]['title']}]({by_id[n]['url']})" for n in cited if n in by_id)
    return md.rstrip() + ("\n\n## References\n" + refs if refs else "")


def planner(state):
    d = llm.complete_json(
        'You are a research planner. Break the question into 3-5 focused subtasks, each with 2 web search queries. '
        'JSON: {"subtasks":[{"task":str,"queries":[str,str]}]}', state["question"])
    subs = [s for s in d.get("subtasks", []) if s.get("queries")]
    if not subs:
        raise ValueError("Planner produced no subtasks")
    return {"plan": subs[:5]}


def researcher(state):
    sources, seen = [], set()
    for sub in state["plan"]:
        for q in sub["queries"][:2]:
            for r in search.web_search(q):
                if r["url"] in seen or len(sources) >= MAX_SOURCES:
                    continue
                seen.add(r["url"])
                text = r["content"]
                if len(text) < 300:
                    try:
                        text = search.fetch_page(r["url"])
                    except requests.RequestException:
                        continue  # unreadable source is dropped, never cited
                if len(text) < 300:
                    continue
                sources.append({"id": len(sources) + 1, "url": r["url"], "title": r["title"],
                                "content": text[:8000], "subtask": sub["task"]})
    if not sources:
        raise ValueError("No source content could be retrieved")
    return {"sources": sources}


EXTRACT = ('You are a fact extractor. From the source text, extract up to 4 factual claims relevant to the question. '
           'Each needs a VERBATIM quote (20-300 chars) copied exactly from the text. '
           'JSON: {"claims":[{"claim":str,"quote":str}]}')
JUDGE = ('You are an entailment judge. For each numbered item decide whether the quote directly supports the claim. '
         'JSON: {"results":[{"i":int,"supported":bool}]}')




def verifier(state):
    claims = []
    sources = state["sources"][:5]

    # Extract claims from each source
    for s in sources:
        d = llm.complete_json(
            EXTRACT,
            f"Question: {state['question']}\n\n"
            f"Source text:\n{s['content'][:3000]}"
        )

        for c in d.get("claims", [])[:2]:
            claim = (c.get("claim") or "").strip()
            quote = (c.get("quote") or "").strip()

            if not claim:
                continue

            found = quote_in_source(quote, s["content"])

            claims.append({
                "source_id": s["id"],
                "claim": claim,
                "quote": quote,
                "status": "pending" if found else "unsupported",
                "reason": "" if found
                else "quote not found in retrieved source text"
            })

    # Verify all pending claims in one LLM call
    pending = [
        c for c in claims
        if c["status"] == "pending"
    ]

    if pending:
        items = "\n\n".join(
            f"{i}. CLAIM: {c['claim']}\nQUOTE: {c['quote']}"
            for i, c in enumerate(pending)
        )

        result = llm.complete_json(JUDGE, items)

        supported = {
            r["i"]
            for r in result.get("results", [])
            if r.get("supported") is True
        }

        for i, c in enumerate(pending):
            c["status"] = (
                "verified" if i in supported else "unsupported"
            )
            c["reason"] = (
                "" if i in supported
                else "quote does not support claim"
            )

    if not any(c["status"] == "verified" for c in claims):
        raise ValueError(
            "No claims could be verified against retrieved sources"
        )

    return {"claims": claims}



def writer(state):
    ver = [c for c in state["claims"] if c["status"] == "verified"]
    facts = "\n".join(f"[{c['source_id']}] {c['claim']}" for c in ver)
    md = llm.complete(
        "Write a structured markdown research report (title, Summary, thematic Findings sections, Limitations). "
        "Use ONLY the verified facts given. Cite every factual sentence with a single-number bracket like [2] "
        "matching the fact's number (one number per bracket, e.g. [1][3]). Never add facts, numbers or sources. "
        "State gaps honestly.", f"Question: {state['question']}\n\nVerified facts:\n{facts}", 3500)
    return {"report": render_citations(md, state["sources"])}


def reviewer(state):
    body = state["report"].split("\n## References")[0]
    prog = [f"Invalid citation [{n}]: not a retrieved source" for n in sorted(set(re.findall(r"\[(\d+)\](?!\()", body)))]
    prog += [f"Uncited paragraph: {p[:60]}..." for p in body.splitlines()
             if len(p) > 80 and not p.startswith("#") and not re.search(r"\[\d+\]\(http", p)]
    facts = "\n".join(f"[{c['source_id']}] {c['claim']}" for c in state["claims"] if c["status"] == "verified")
    d = llm.complete_json(
        "You are a QA reviewer. Compare the report to the verified facts. List report claims not supported by the "
        "facts, contradictions, and quality problems. "
        'JSON: {"issues":[str],"score":int 1-10,"summary":str}', f"FACTS:\n{facts}\n\nREPORT:\n{body}")
    score = int(d.get("score", 0))
    return {"review": {"issues": prog + list(d.get("issues", [])), "score": score,
                       "summary": d.get("summary", ""), "passed": not prog and score >= 7}}
