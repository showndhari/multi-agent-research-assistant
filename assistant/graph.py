import time
from typing import TypedDict
import requests
from langgraph.graph import StateGraph, END
from . import agents
from .llm import ConfigError, ServiceError

ORDER = [("Planner", agents.planner), ("Research", agents.researcher), ("Verification", agents.verifier),
         ("Writer", agents.writer), ("Review", agents.reviewer)]
NAMES = [n for n, _ in ORDER]


class State(TypedDict, total=False):
    question: str
    plan: list
    sources: list
    claims: list
    report: str
    review: dict
    statuses: dict
    error: str


def _wrap(name, fn):
    def run(state):
        st, t = dict(state.get("statuses", {})), time.time()
        try:
            out = fn(state)
            st[name] = {"status": "completed", "seconds": round(time.time() - t, 1)}
            return {**out, "statuses": st}
        except (ConfigError, ServiceError, requests.RequestException, ValueError, KeyError, TypeError) as e:
            st[name] = {"status": "failed", "error": str(e)}
            return {"statuses": st, "error": f"{name} agent failed: {e}"}
    return run


def build():
    g = StateGraph(State)
    for n, f in ORDER:
        g.add_node(n, _wrap(n, f))
    g.set_entry_point(NAMES[0])
    for i, n in enumerate(NAMES):
        nxt = NAMES[i + 1] if i + 1 < len(NAMES) else END
        g.add_conditional_edges(n, lambda s, nxt=nxt: END if s.get("error") else nxt)
    return g.compile()
