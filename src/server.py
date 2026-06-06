"""
dag-headroom MCP server — single tool, single entry point.
"""

import sqlite3
import os
from datetime import datetime
from typing import Literal, Optional

from fastmcp import FastMCP

from .compressor import compress, estimate_tokens

# ---------------------------------------------------------------------------
# DB path — default next to this file, overridable for tests
# ---------------------------------------------------------------------------

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "dag_headroom.db")


# ---------------------------------------------------------------------------
# T01: init_db — 4 tables, WAL mode
# ---------------------------------------------------------------------------

def init_db(path: str = _DEFAULT_DB) -> None:
    with _db(path) as conn:
        conn.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                description TEXT,
                tokens_saved INT DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS nodes (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT NOT NULL,
                name         TEXT NOT NULL,
                thought_type TEXT NOT NULL,
                payload      TEXT NOT NULL,
                compressed   TEXT,
                ccr_hash     TEXT NOT NULL,
                note         TEXT DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'COMPLETED',
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, name)
            );

            CREATE TABLE IF NOT EXISTS edges (
                session_id TEXT NOT NULL,
                parent     TEXT NOT NULL,
                child      TEXT NOT NULL,
                PRIMARY KEY (session_id, parent, child)
            );

            CREATE TABLE IF NOT EXISTS ccr_store (
                hash       TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                node_name  TEXT NOT NULL,
                original   TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)


# ---------------------------------------------------------------------------
# T02: _db — connection helper with row_factory and busy_timeout
# ---------------------------------------------------------------------------

def _db(path: str = _DEFAULT_DB):
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


# ---------------------------------------------------------------------------
# T03: _ensure_session — INSERT OR IGNORE
# ---------------------------------------------------------------------------

def _ensure_session(conn: sqlite3.Connection, session_id: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO sessions (id) VALUES (?)",
        (session_id,),
    )


# ---------------------------------------------------------------------------
# T04: _has_cycle — DFS cycle detection
# ---------------------------------------------------------------------------

def _has_cycle(conn: sqlite3.Connection, session_id: str, new_parent: str, new_child: str) -> bool:
    """Return True if adding edge new_parent→new_child would create a cycle."""
    # Build adjacency: child → [parents] (reverse edges for ancestor search)
    rows = conn.execute(
        "SELECT parent, child FROM edges WHERE session_id=?", (session_id,)
    ).fetchall()
    graph: dict[str, list[str]] = {}
    for row in rows:
        graph.setdefault(row["child"], []).append(row["parent"])

    # Also add the prospective edge
    graph.setdefault(new_child, []).append(new_parent)

    # DFS from new_parent — can we reach new_child through existing parents?
    # Equivalently: can we reach new_parent starting from new_child?
    visited = set()
    stack = [new_child]
    while stack:
        node = stack.pop()
        if node == new_parent:
            return True
        if node in visited:
            continue
        visited.add(node)
        # Walk from child's perspective upward through parents
        # (we're checking if new_parent is an ancestor of new_child)
        # Use forward direction instead: from new_parent, can we reach new_child?

    # Reset: use forward edges to check if new_child is reachable from new_parent
    forward: dict[str, list[str]] = {}
    for row in rows:
        forward.setdefault(row["parent"], []).append(row["child"])

    visited = set()
    stack = [new_parent]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        for child in forward.get(node, []):
            if child == new_child:
                return True
            stack.append(child)

    # Also check if new_child already transitively points to new_parent
    # (would create a cycle via the new edge)
    visited = set()
    stack = [new_child]
    while stack:
        node = stack.pop()
        if node == new_parent:
            return True
        if node in visited:
            continue
        visited.add(node)
        for child in forward.get(node, []):
            stack.append(child)

    return False


# ---------------------------------------------------------------------------
# T05: _cascade_invalidate — recursive DFS, returns affected names
# ---------------------------------------------------------------------------

def _cascade_invalidate(conn: sqlite3.Connection, session_id: str, root: str) -> list[str]:
    rows = conn.execute(
        "SELECT parent, child FROM edges WHERE session_id=?", (session_id,)
    ).fetchall()
    children: dict[str, list[str]] = {}
    for row in rows:
        children.setdefault(row["parent"], []).append(row["child"])

    affected = []
    stack = [root]
    visited = set()
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        affected.append(node)
        for child in children.get(node, []):
            stack.append(child)

    conn.executemany(
        "UPDATE nodes SET status='INVALIDATED' WHERE session_id=? AND name=?",
        [(session_id, n) for n in affected],
    )
    return affected


# ---------------------------------------------------------------------------
# Core logic — separated from FastMCP layer for testability
# ---------------------------------------------------------------------------

def call_dag_headroom(
    *,
    db_path: str = _DEFAULT_DB,
    action: str,
    session_id: str,
    node_name: Optional[str] = None,
    thought_type: Optional[str] = None,
    payload: Optional[str] = None,
    depends_on: Optional[list[str]] = None,
    note: str = "",
    target_node: Optional[str] = None,
    reason: str = "",
    ccr_hash: Optional[str] = None,
) -> dict:
    init_db(db_path)

    if action == "think":
        return _action_think(
            db_path=db_path,
            session_id=session_id,
            node_name=node_name,
            thought_type=thought_type,
            payload=payload,
            depends_on=depends_on or [],
            note=note,
        )
    elif action == "status":
        return _action_status(db_path=db_path, session_id=session_id)
    elif action == "invalidate":
        return _action_invalidate(
            db_path=db_path,
            session_id=session_id,
            target_node=target_node,
            reason=reason,
        )
    elif action == "restore":
        return _action_restore(
            db_path=db_path,
            session_id=session_id,
            ccr_hash_val=ccr_hash,
        )
    else:
        raise ValueError(
            f"Unknown action: '{action}'. Must be one of: think, status, invalidate, restore"
        )


# ---------------------------------------------------------------------------
# action="think"
# ---------------------------------------------------------------------------

VALID_THOUGHT_TYPES = frozenset({
    "Objective", "Hypothesis", "Assumption",
    "Evidence", "Critique", "Synthesis", "Action",
})


def _action_think(
    *,
    db_path: str,
    session_id: str,
    node_name: Optional[str],
    thought_type: Optional[str],
    payload: Optional[str],
    depends_on: list[str],
    note: str,
) -> dict:
    # --- validation ---
    if not node_name:
        raise ValueError("node_name is required for action='think'")
    if not thought_type or thought_type not in VALID_THOUGHT_TYPES:
        raise ValueError(f"thought_type must be one of: {sorted(VALID_THOUGHT_TYPES)}")
    if not payload:
        raise ValueError("payload is required for action='think'")
    if len(payload) < 80:
        raise ValueError("payload must be at least 80 characters")
    if len(payload) > 1500:
        raise ValueError("payload must be at most 1500 characters")

    with _db(db_path) as conn:
        _ensure_session(conn, session_id)

        # --- cycle detection ---
        for parent in depends_on:
            if parent == node_name:
                raise ValueError(f"Cycle detected: '{node_name}' cannot depend on itself")
            if _has_cycle(conn, session_id, parent, node_name):
                raise ValueError(
                    f"Cycle detected: adding edge {parent}→{node_name} would create a cycle"
                )

        # --- parent_context: auto-resolve depends_on ---
        parent_context = {}
        for parent_name in depends_on:
            row = conn.execute(
                "SELECT thought_type, payload, compressed, ccr_hash, status "
                "FROM nodes WHERE session_id=? AND name=?",
                (session_id, parent_name),
            ).fetchone()
            if row is None:
                parent_context[parent_name] = {"error": f"Node '{parent_name}' not found"}
                continue

            entry = {
                "thought_type": row["thought_type"],
                "ccr_hash": row["ccr_hash"],
                "is_compressed": row["compressed"] is not None,
            }
            entry["payload"] = row["compressed"] if row["compressed"] else row["payload"]

            if row["status"] == "INVALIDATED":
                entry["warning"] = f"Parent node '{parent_name}' is INVALIDATED — review before proceeding"
                entry["is_invalidated"] = True

            parent_context[parent_name] = entry

        # --- compress payload ---
        compressed_text, hash_val, tokens_saved = compress(payload)
        is_compressed = compressed_text != payload

        # --- upsert node ---
        existing = conn.execute(
            "SELECT id FROM nodes WHERE session_id=? AND name=?",
            (session_id, node_name),
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE nodes
                   SET thought_type=?, payload=?, compressed=?, ccr_hash=?,
                       note=?, status='COMPLETED', created_at=CURRENT_TIMESTAMP
                   WHERE session_id=? AND name=?""",
                (
                    thought_type, payload,
                    compressed_text if is_compressed else None,
                    hash_val, note,
                    session_id, node_name,
                ),
            )
            op_status = "updated"
        else:
            conn.execute(
                """INSERT INTO nodes
                   (session_id, name, thought_type, payload, compressed, ccr_hash, note, status)
                   VALUES (?,?,?,?,?,?,?,'COMPLETED')""",
                (
                    session_id, node_name, thought_type, payload,
                    compressed_text if is_compressed else None,
                    hash_val, note,
                ),
            )
            op_status = "created"

        # --- store original in ccr_store (always) ---
        conn.execute(
            """INSERT OR REPLACE INTO ccr_store (hash, session_id, node_name, original)
               VALUES (?,?,?,?)""",
            (hash_val, session_id, node_name, payload),
        )

        # --- record edges ---
        for parent in depends_on:
            conn.execute(
                "INSERT OR IGNORE INTO edges (session_id, parent, child) VALUES (?,?,?)",
                (session_id, parent, node_name),
            )

        # --- update session aggregate ---
        conn.execute(
            "UPDATE sessions SET tokens_saved = tokens_saved + ? WHERE id=?",
            (tokens_saved, session_id),
        )

        conn.commit()

    result: dict = {
        "status": op_status,
        "node": node_name,
        "ccr_hash": hash_val,
        "compression": {
            "tokens_saved": tokens_saved,
        },
        "next_hint": "Add Evidence/Critique or call status() to close.",
    }

    if parent_context:
        result["parent_context"] = parent_context

    return result


# ---------------------------------------------------------------------------
# action="status"
# ---------------------------------------------------------------------------

def _action_status(*, db_path: str, session_id: str) -> dict:
    with _db(db_path) as conn:
        _ensure_session(conn, session_id)

        node_rows = conn.execute(
            "SELECT name, thought_type, ccr_hash, status FROM nodes "
            "WHERE session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()

        edge_rows = conn.execute(
            "SELECT parent, child FROM edges WHERE session_id=?",
            (session_id,),
        ).fetchall()

        payload_rows = conn.execute(
            "SELECT payload, compressed FROM nodes WHERE session_id=?",
            (session_id,),
        ).fetchall()

        session_row = conn.execute(
            "SELECT tokens_saved FROM sessions WHERE id=?",
            (session_id,),
        ).fetchone()

    # metrics
    tokens_original = sum(estimate_tokens(r["payload"]) for r in payload_rows)
    tokens_compressed = sum(
        estimate_tokens(r["compressed"]) if r["compressed"] else estimate_tokens(r["payload"])
        for r in payload_rows
    )
    tokens_saved = (session_row["tokens_saved"] if session_row else 0)
    ratio = (1 - tokens_compressed / tokens_original) if tokens_original > 0 else 0.0

    # restoration manifest
    manifest_nodes = []
    for row in node_rows:
        manifest_nodes.append({
            "name": row["name"],
            "type": row["thought_type"],
            "status": row["status"],
            "ccr_hash": row["ccr_hash"],
            "restore_cmd": (
                f"dag_headroom(action='restore', "
                f"session_id='{session_id}', "
                f"ccr_hash='{row['ccr_hash']}')"
            ),
        })

    return {
        "session_id": session_id,
        "dag": {
            "nodes": [
                {"name": r["name"], "thought_type": r["thought_type"], "status": r["status"]}
                for r in node_rows
            ],
            "edges": [{"parent": r["parent"], "child": r["child"]} for r in edge_rows],
        },
        "metrics": {
            "tokens_original": tokens_original,
            "tokens_compressed": tokens_compressed,
            "tokens_saved": tokens_saved,
            "ratio": round(ratio, 4),
        },
        "restoration_manifest": {
            "how_to_restore": (
                "dag_headroom(action='restore', session_id='<id>', ccr_hash='<hash>')"
            ),
            "nodes": manifest_nodes,
        },
    }


# ---------------------------------------------------------------------------
# action="invalidate"
# ---------------------------------------------------------------------------

def _action_invalidate(
    *, db_path: str, session_id: str, target_node: Optional[str], reason: str
) -> dict:
    if not target_node:
        raise ValueError("target_node is required for action='invalidate'")

    with _db(db_path) as conn:
        _ensure_session(conn, session_id)
        affected = _cascade_invalidate(conn, session_id, target_node)
        conn.commit()

    return {
        "invalidated": affected,
        "reason": reason,
        "hint": "Re-create with corrected analysis.",
    }


# ---------------------------------------------------------------------------
# action="restore"
# ---------------------------------------------------------------------------

def _action_restore(
    *, db_path: str, session_id: str, ccr_hash_val: Optional[str]
) -> dict:
    with _db(db_path) as conn:
        _ensure_session(conn, session_id)

        if ccr_hash_val is None:
            # list all restorable nodes in this session
            rows = conn.execute(
                "SELECT name, ccr_hash FROM nodes WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
            return {
                "restorable_nodes": [
                    {
                        "name": r["name"],
                        "ccr_hash": r["ccr_hash"],
                        "restore_cmd": (
                            f"dag_headroom(action='restore', "
                            f"session_id='{session_id}', "
                            f"ccr_hash='{r['ccr_hash']}')"
                        ),
                    }
                    for r in rows
                ]
            }

        # C18: session scoping — hash must belong to this session
        row = conn.execute(
            "SELECT node_name, original FROM ccr_store "
            "WHERE hash=? AND session_id=?",
            (ccr_hash_val, session_id),
        ).fetchone()

        if row is None:
            # Check if hash exists in another session
            other = conn.execute(
                "SELECT session_id FROM ccr_store WHERE hash=?",
                (ccr_hash_val,),
            ).fetchone()
            if other:
                raise ValueError(
                    f"Hash '{ccr_hash_val}' belongs to session '{other['session_id']}', "
                    f"not '{session_id}'"
                )
            raise ValueError(f"Hash '{ccr_hash_val}' not found")

        tokens = estimate_tokens(row["original"])
        return {
            "node_name": row["node_name"],
            "original_payload": row["original"],
            "tokens": tokens,
        }


# ---------------------------------------------------------------------------
# FastMCP tool — C01: exactly one tool exposed
# ---------------------------------------------------------------------------

mcp = FastMCP("dag-headroom")


@mcp.tool()
def dag_headroom(
    action: Literal["think", "status", "invalidate", "restore"],
    session_id: str,
    node_name: Optional[str] = None,
    thought_type: Optional[Literal[
        "Objective", "Hypothesis", "Assumption",
        "Evidence", "Critique", "Synthesis", "Action"
    ]] = None,
    payload: Optional[str] = None,
    depends_on: list[str] = [],
    note: str = "",
    target_node: Optional[str] = None,
    reason: str = "",
    ccr_hash: Optional[str] = None,
) -> dict:
    """
    Single entry point for DAG-structured reasoning with automatic CCR context compression.

    action="think"      — create/update a reasoning node (node_name, thought_type, payload required)
    action="status"     — show DAG topology, metrics, and restoration manifest
    action="invalidate" — cascade-invalidate a node and its descendants (target_node required)
    action="restore"    — retrieve original payload by ccr_hash; omit hash to list all restorable nodes
    """
    return call_dag_headroom(
        action=action,
        session_id=session_id,
        node_name=node_name,
        thought_type=thought_type,
        payload=payload,
        depends_on=depends_on,
        note=note,
        target_node=target_node,
        reason=reason,
        ccr_hash=ccr_hash,
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
