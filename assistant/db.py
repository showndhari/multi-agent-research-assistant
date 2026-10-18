import json, os, sqlite3, datetime as dt
from contextlib import closing


def _conn():
    c = sqlite3.connect(os.getenv("DB_PATH", "research.db"))
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT,"
              " question TEXT, status TEXT, error TEXT, report TEXT, state TEXT)")
    return c


def save_run(state):
    with closing(_conn()) as c:
        cur = c.execute("INSERT INTO runs(created,question,status,error,report,state) VALUES(?,?,?,?,?,?)",
                        (dt.datetime.now().isoformat(timespec="seconds"), state["question"],
                         "failed" if state.get("error") else "completed", state.get("error"),
                         state.get("report"), json.dumps(state)))
        c.commit()
        return cur.lastrowid


def list_runs():
    with closing(_conn()) as c:
        return [dict(r) for r in c.execute("SELECT id,created,question,status FROM runs ORDER BY id DESC LIMIT 50")]


def get_run(run_id):
    with closing(_conn()) as c:
        r = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["state"] = json.loads(d["state"])
    return d
