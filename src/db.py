"""dag-thinking DB primitives — connection, schema, graph utilities."""

import contextlib
import os
import sqlite3

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
