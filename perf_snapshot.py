"""Perf measurement tool (Method R): snapshot pg_stat_statements + table sizes, then diff.

Read-only. Proof = response time of a named task, before (b) vs after (a).
This tool gives the raw b/a numbers; pair it with EXPLAIN (ANALYZE, BUFFERS) on the
witness query of each parcours. See Trello card "Mesurer les impacts" (dEaKIH57).

Usage (from mobilic-api/):
  pipenv run python perf_snapshot.py snapshot before     # -> perf_snap_before.json
  pipenv run python perf_snapshot.py snapshot after
  pipenv run python perf_snapshot.py diff perf_snap_before.json perf_snap_after.json
  pipenv run python perf_snapshot.py selftest            # offline check of diff logic
"""

import json
import math
import os
import sys

# ponytail: heap+index size tracked for these tables only (the pg_repack targets);
# add a name here if a new card touches another table.
PERF_TABLES = [
    "activity",
    "activity_version",
    "mission_validation",
    "regulatory_alert",
    "location_entry",
    "regulation_computation",
]


def human(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def capture():
    """Read pg_stat_statements (top 100 by total time) + table sizes. Read-only."""
    from app import db, app
    from sqlalchemy import text

    stmt_sql = (
        "SELECT queryid, calls, total_exec_time, mean_exec_time, rows, "
        "shared_blks_hit, shared_blks_read, "
        "left(regexp_replace(query, '\\s+', ' ', 'g'), 120) AS q "
        "FROM pg_stat_statements WHERE queryid IS NOT NULL "
        "ORDER BY total_exec_time DESC LIMIT 100"
    )
    size_sql = (
        "SELECT relname, pg_total_relation_size(c.oid), pg_relation_size(c.oid), "
        "pg_indexes_size(c.oid) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r'"
    )
    with app.app_context():
        db.session.execute(text("SET default_transaction_read_only = on"))
        db.session.execute(text("SET statement_timeout = '15s'"))
        db.session.execute(text("SET lock_timeout = '1s'"))
        stmts = []
        for r in db.session.execute(text(stmt_sql)).fetchall():
            stmts.append(
                {
                    "queryid": str(r[0]),
                    "calls": int(r[1]),
                    "total_ms": float(r[2]),
                    "mean_ms": float(r[3]),
                    "rows": int(r[4]),
                    "hit": int(r[5]),
                    "read": int(r[6]),
                    "q": r[7],
                }
            )
        sizes = {}
        for r in db.session.execute(text(size_sql)).fetchall():
            if r[0] in PERF_TABLES:
                sizes[r[0]] = {
                    "total": int(r[1]),
                    "heap": int(r[2]),
                    "idx": int(r[3]),
                }
    return {"statements": stmts, "sizes": sizes}


def compute_diff(before, after):
    """Pure function: b/a deltas per query (matched by queryid) and per table size."""
    b = {s["queryid"]: s for s in before["statements"]}
    a = {s["queryid"]: s for s in after["statements"]}
    changed = []
    for qid in set(b) | set(a):
        sb, sa = b.get(qid), a.get(qid)
        mean_b = sb["mean_ms"] if sb else 0.0
        mean_a = sa["mean_ms"] if sa else 0.0
        calls_b = sb["calls"] if sb else 0
        calls_a = sa["calls"] if sa else 0
        pct = ((mean_a - mean_b) / mean_b * 100) if mean_b else None
        changed.append(
            {
                "queryid": qid,
                "q": (sa or sb)["q"],
                "mean_b": round(mean_b, 2),
                "mean_a": round(mean_a, 2),
                "mean_pct": round(pct, 1) if pct is not None else None,
                "calls_b": calls_b,
                "calls_a": calls_a,
            }
        )
    # biggest mean-time movers first (improvement or regression)
    changed.sort(key=lambda c: abs(c["mean_a"] - c["mean_b"]), reverse=True)

    sizes = []
    for t in PERF_TABLES:
        tb = before["sizes"].get(t, {}).get("total", 0)
        ta = after["sizes"].get(t, {}).get("total", 0)
        sizes.append(
            {"table": t, "before": tb, "after": ta, "recovered": tb - ta}
        )
    sizes.sort(key=lambda s: s["recovered"], reverse=True)
    return {"statements": changed, "sizes": sizes}


def print_diff(d):
    print("== Table size (b -> a, recovered) ==")
    for s in d["sizes"]:
        print(
            f"  {s['table']:<22} {human(s['before']):>10} -> {human(s['after']):>10}  "
            f"recovered {human(s['recovered'])}"
        )
    print("\n== Query mean_exec_time (b -> a), top 25 movers ==")
    for c in d["statements"][:25]:
        pct = f"{c['mean_pct']:+.1f}%" if c["mean_pct"] is not None else "new"
        print(
            f"  {c['mean_b']:>8.1f} -> {c['mean_a']:>8.1f} ms ({pct:>7})  "
            f"calls {c['calls_b']}->{c['calls_a']}  {c['q'][:80]}"
        )


def selftest():
    before = {
        "statements": [
            {
                "queryid": "1",
                "calls": 100,
                "total_ms": 1000,
                "mean_ms": 10.0,
                "rows": 1,
                "hit": 1,
                "read": 1,
                "q": "SELECT slow",
            },
            {
                "queryid": "2",
                "calls": 5000,
                "total_ms": 500,
                "mean_ms": 0.1,
                "rows": 1,
                "hit": 1,
                "read": 1,
                "q": "SELECT n+1",
            },
        ],
        "sizes": {
            "mission_validation": {"total": 7_000_000_000, "heap": 0, "idx": 0}
        },
    }
    after = {
        "statements": [
            {
                "queryid": "1",
                "calls": 100,
                "total_ms": 100,
                "mean_ms": 1.0,
                "rows": 1,
                "hit": 1,
                "read": 1,
                "q": "SELECT slow",
            },
            # query 2 (the N+1) disappeared after the fix
        ],
        "sizes": {
            "mission_validation": {"total": 4_000_000_000, "heap": 0, "idx": 0}
        },
    }
    d = compute_diff(before, after)
    q1 = next(c for c in d["statements"] if c["queryid"] == "1")
    assert math.isclose(q1["mean_pct"], -90.0), q1
    q2 = next(c for c in d["statements"] if c["queryid"] == "2")
    assert (
        math.isclose(q2["mean_a"], 0.0, abs_tol=1e-9) and q2["calls_a"] == 0
    ), q2  # N+1 query gone
    mv = next(s for s in d["sizes"] if s["table"] == "mission_validation")
    assert mv["recovered"] == 3_000_000_000, mv
    # path traversal is neutralized: a "../" input stays inside the working dir
    base = os.path.realpath(os.getcwd())
    assert _safe_path("../../etc/passwd") == os.path.join(base, "passwd")
    print("selftest OK")


def _safe_path(name):
    """Resolve a snapshot file name within the working dir (no path traversal)."""
    base = os.path.realpath(os.getcwd())
    full = os.path.realpath(os.path.join(base, os.path.basename(name)))
    if os.path.commonpath([base, full]) != base:
        raise ValueError(f"refusing path outside {base}: {name!r}")
    return full


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "snapshot":
        label = sys.argv[2] if len(sys.argv) > 2 else "snap"
        path = _safe_path(f"perf_snap_{label}.json")
        with open(path, "w") as f:
            json.dump(capture(), f, indent=2)
        print(f"wrote {path}")
    elif cmd == "diff":
        with open(_safe_path(sys.argv[2])) as f:
            before = json.load(f)
        with open(_safe_path(sys.argv[3])) as f:
            after = json.load(f)
        print_diff(compute_diff(before, after))
    elif cmd == "selftest":
        selftest()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
