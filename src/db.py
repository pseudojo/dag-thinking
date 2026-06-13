"""dag-thinking DB primitives — connection, schema, graph utilities."""

import contextlib
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "dag_thinking.db")


def init_db(path: str = _DEFAULT_DB) -> None:
    with contextlib.closing(_db(path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id           TEXT PRIMARY KEY,
                    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                    description  TEXT,
                    tokens_saved INT DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id      TEXT NOT NULL,
                    name            TEXT NOT NULL,
                    thought_type    TEXT NOT NULL,
                    payload         TEXT NOT NULL,
                    compressed      TEXT,
                    ccr_hash        TEXT NOT NULL,
                    note            TEXT DEFAULT '',
                    status          TEXT NOT NULL DEFAULT 'COMPLETED',
                    tokens_original INT NOT NULL DEFAULT 0,
                    tokens_saved    INT NOT NULL DEFAULT 0,
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(session_id, name)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    session_id TEXT NOT NULL,
                    parent     TEXT NOT NULL,
                    child      TEXT NOT NULL,
                    PRIMARY KEY (session_id, parent, child)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ccr_store (
                    hash       TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    node_name  TEXT NOT NULL,
                    original   TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (hash, session_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_nodes_session_status
                ON nodes(session_id, status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_edges_child
                ON edges(session_id, child)
            """)


def _db(path: str = _DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def _ensure_session(conn: sqlite3.Connection, session_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO sessions (id) VALUES (?)",
        (session_id,),
    )


def _load_forward_edges(
    conn: sqlite3.Connection,
    session_id: str,
) -> dict[str, list[str]]:
    """session_id의 모든 forward-edge를 인접 리스트로 반환 (단 1회 DB 조회)."""
    rows = conn.execute(
        "SELECT parent, child FROM edges WHERE session_id=?", (session_id,)
    ).fetchall()
    graph: dict[str, list[str]] = {}
    for row in rows:
        graph.setdefault(row["parent"], []).append(row["child"])
    return graph


def _has_cycle_graph(
    graph: dict[str, list[str]],
    new_parent: str,
    new_child: str,
) -> bool:
    """Pre-loaded graph으로 사이클 감지 — DB 접근 없음. self-reference 즉시 처리."""
    if new_parent == new_child:
        return True
    visited: set[str] = set()
    stack = [new_child]
    while stack:
        node = stack.pop()
        if node == new_parent:
            return True
        if node in visited:
            continue
        visited.add(node)
        stack.extend(graph.get(node, []))
    return False


def _cascade_invalidate(
    conn: sqlite3.Connection,
    session_id: str,
    root: str,
) -> list[str]:
    forward_graph = _load_forward_edges(conn, session_id)

    reachable: list[str] = []
    stack = [root]
    visited: set[str] = set()
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        reachable.append(node)
        for child in forward_graph.get(node, []):
            stack.append(child)

    if not reachable:
        return []

    placeholders = ", ".join("?" * len(reachable))
    status_rows = conn.execute(
        f"SELECT name, status FROM nodes WHERE session_id=? AND name IN ({placeholders})",
        [session_id, *reachable],
    ).fetchall()
    newly = [r["name"] for r in status_rows if r["status"] != "INVALIDATED"]

    if not newly:
        return []

    conn.executemany(
        "UPDATE nodes SET status='INVALIDATED' WHERE session_id=? AND name=?",
        [(session_id, n) for n in newly],
    )
    return newly


def get_archive_db_path(db_path: str) -> str:

    db_dir = os.path.dirname(os.path.abspath(db_path))
    today = date.today().strftime("%Y%m%d")
    return os.path.join(db_dir, f"dag-thinking-archive-{today}.db")


def _get_cleanup_candidates(
    conn: sqlite3.Connection,
    current_session_id: str,
    max_age_days: int,
    max_count: int,
) -> list[str]:

    candidates: set[str] = set()

    if max_age_days > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        rows = conn.execute(
            "SELECT id FROM sessions WHERE created_at < ? AND id != ?",
            (cutoff, current_session_id),
        ).fetchall()
        candidates.update(r["id"] for r in rows)

    if max_count > 0:
        total = conn.execute("SELECT count(*) FROM sessions").fetchone()[0]
        excess = total - max_count
        if excess > 0:
            rows = conn.execute(
                "SELECT id FROM sessions WHERE id != ? ORDER BY created_at ASC LIMIT ?",
                (current_session_id, excess),
            ).fetchall()
            candidates.update(r["id"] for r in rows)

    return list(candidates)


def _delete_sessions(conn: sqlite3.Connection, session_ids: list[str]) -> int:
    if not session_ids:
        return 0
    ph = ",".join("?" * len(session_ids))
    conn.execute(f"DELETE FROM ccr_store WHERE session_id IN ({ph})", session_ids)
    conn.execute(f"DELETE FROM edges WHERE session_id IN ({ph})", session_ids)
    conn.execute(f"DELETE FROM nodes WHERE session_id IN ({ph})", session_ids)
    conn.execute(f"DELETE FROM sessions WHERE id IN ({ph})", session_ids)
    return len(session_ids)


def _archive_sessions(
    db_path: str,
    session_ids: list[str],
    archive_db_path: str,
) -> int:
    if not session_ids:
        return 0
    init_db(archive_db_path)
    ph = ",".join("?" * len(session_ids))
    with contextlib.closing(_db(db_path)) as src:
        sessions = src.execute(f"SELECT * FROM sessions WHERE id IN ({ph})", session_ids).fetchall()
        nodes = src.execute(
            f"SELECT * FROM nodes WHERE session_id IN ({ph})", session_ids
        ).fetchall()
        edges = src.execute(
            f"SELECT * FROM edges WHERE session_id IN ({ph})", session_ids
        ).fetchall()
        ccr = src.execute(
            f"SELECT * FROM ccr_store WHERE session_id IN ({ph})", session_ids
        ).fetchall()

    with contextlib.closing(_db(archive_db_path)) as dst:
        with dst:
            for r in sessions:
                dst.execute(
                    "INSERT OR IGNORE INTO sessions (id, created_at, description, tokens_saved)"
                    " VALUES (?, ?, ?, ?)",
                    (r["id"], r["created_at"], r["description"], r["tokens_saved"]),
                )
            for r in nodes:
                dst.execute(
                    "INSERT OR IGNORE INTO nodes"
                    " (session_id, name, thought_type, payload, compressed, ccr_hash,"
                    "  note, status, tokens_original, tokens_saved, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        r["session_id"],
                        r["name"],
                        r["thought_type"],
                        r["payload"],
                        r["compressed"],
                        r["ccr_hash"],
                        r["note"],
                        r["status"],
                        r["tokens_original"],
                        r["tokens_saved"],
                        r["created_at"],
                    ),
                )
            for r in edges:
                dst.execute(
                    "INSERT OR IGNORE INTO edges (session_id, parent, child) VALUES (?, ?, ?)",
                    (r["session_id"], r["parent"], r["child"]),
                )
            for r in ccr:
                dst.execute(
                    "INSERT OR IGNORE INTO ccr_store"
                    " (hash, session_id, node_name, original, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (r["hash"], r["session_id"], r["node_name"], r["original"], r["created_at"]),
                )

    with contextlib.closing(_db(db_path)) as conn:
        with conn:
            _delete_sessions(conn, session_ids)

    return len(session_ids)


def cleanup_if_needed(
    db_path: str,
    current_session_id: str,
    max_age_days: int = 30,
    max_count: int = 500,
    policy: str = "delete",
) -> int:
    if policy not in ("delete", "archive"):
        raise ValueError(f"Invalid policy '{policy}': must be 'delete' or 'archive'")

    with contextlib.closing(_db(db_path)) as conn:
        candidates = _get_cleanup_candidates(conn, current_session_id, max_age_days, max_count)

    if not candidates:
        return 0

    if policy == "delete":
        with contextlib.closing(_db(db_path)) as conn:
            with conn:
                return _delete_sessions(conn, candidates)

    archive_path = get_archive_db_path(db_path)
    return _archive_sessions(db_path, candidates, archive_path)
