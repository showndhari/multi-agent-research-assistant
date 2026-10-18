import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
from assistant import db, graph  # noqa: E402

st.set_page_config(page_title="Research & Evidence Assistant", layout="wide")
st.title("Multi-Agent Research & Evidence Assistant")
missing = [k for k in ("GROQ_API_KEY", "TAVILY_API_KEY") if not os.getenv(k)]
if missing:
    st.error(f"Missing environment variables: {', '.join(missing)}. See README.")
    st.stop()


def show_status(box, state, running):
    stt, lines, pending_shown = state.get("statuses", {}), [], False
    for n in graph.NAMES:
        if n in stt:
            s = stt[n]
            lines.append(f"{'✅' if s['status'] == 'completed' else '❌'} **{n}** - {s['status']}"
                         + (f" ({s['seconds']}s)" if "seconds" in s else f": {s.get('error')}"))
        elif state.get("error") or not running:
            lines.append(f"⏹ **{n}** - not run")
        elif not pending_shown:
            lines.append(f"⏳ **{n}** - running"); pending_shown = True
        else:
            lines.append(f"⚪ **{n}** - pending")
    box.markdown("\n\n".join(lines))


def show_result(state):
    if state.get("error"):
        st.error(state["error"])

    if state.get("report"):
        report = state["report"]

        st.markdown(report)

        st.download_button(
            label="📥 Download Report (Markdown)",
            data=report,
            file_name="research_report.md",
            mime="text/markdown",
        )

    rv = state.get("review")
    if rv:
        (st.success if rv["passed"] else st.warning)(
            f"Quality review: "
            f"{'passed' if rv['passed'] else 'issues found'} "
            f"- score {rv['score']}/10. {rv['summary']}"
        )

        for i in rv["issues"]:
            st.markdown(f"- {i}")

    if state.get("claims"):
        with st.expander("Claim verification details"):
            for c in state["claims"]:
                src = next(
                    (
                        s for s in state["sources"]
                        if s["id"] == c["source_id"]
                    ),
                    None,
                )

                source_url = src["url"] if src else "#"

                st.markdown(
                    f"**{c['status'].upper()}** "
                    f"[{c['source_id']}]({source_url}): "
                    f"{c['claim']}"
                    + (f"  \n> {c['quote']}" if c["quote"] else "")
                    + (
                        f"  \n_{c['reason']}_"
                        if c.get("reason") else ""
                    )
                )
    rv = state.get("review")
    if rv:
        (st.success if rv["passed"] else st.warning)(f"Quality review: {'passed' if rv['passed'] else 'issues found'} - score {rv['score']}/10. {rv['summary']}")
        for i in rv["issues"]:
            st.markdown(f"- {i}")
    if state.get("claims"):
        with st.expander("Claim verification details"):
            for c in state["claims"]:
                src = next((s for s in state["sources"] if s["id"] == c["source_id"]), None)
                st.markdown(f"**{c['status'].upper()}** [{c['source_id']}]({src['url']}): {c['claim']}"
                            + (f"  \n> {c['quote']}" if c["quote"] else "") + (f"  \n_{c['reason']}_" if c.get("reason") else ""))


with st.sidebar:
    st.header("History")
    runs = db.list_runs()
    pick = st.selectbox("Past runs", [None] + [r["id"] for r in runs], format_func=lambda i: "-" if i is None else
                        next(f"#{r['id']} {r['status']}: {r['question'][:40]}" for r in runs if r["id"] == i))

if pick:
    run = db.get_run(pick)
    st.caption(f"Run #{pick} - {run['created']}")
    show_status(st.container(), run["state"], False)
    show_result(run["state"])
else:
    q = st.text_area("Research question", height=80)
    if st.button("Run research", type="primary") and q.strip():
        box, state = st.empty(), {"question": q.strip()}
        show_status(box, state, True)
        for state in graph.build().stream(state, stream_mode="values"):
            show_status(box, state, True)
        show_status(box, state, False)
        db.save_run(state)
        show_result(state)
