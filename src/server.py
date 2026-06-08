"""
dag-thinking MCP server — single tool, single entry point.
"""

import contextlib
import os
import sqlite3
from collections import deque
from typing import Literal

from fastmcp import FastMCP

from .compressor import compress, estimate_tokens

# ---------------------------------------------------------------------------
# DB path — default next to this file, overridable for tests
# ---------------------------------------------------------------------------

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "dag_thinking.db")


# ---------------------------------------------------------------------------
# T01: init_db — 4 tables, WAL mode
# ---------------------------------------------------------------------------

def init_db(path: str = _DEFAULT_DB) -> None:
    with contextlib.closing(_db(path)) as conn:
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

            CREATE INDEX IF NOT EXISTS idx_nodes_session_status
                ON nodes(session_id, status);
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
# T04: _has_cycle — DFS cycle detection (I01: simplified to single DFS)
# ---------------------------------------------------------------------------

def _has_cycle(conn: sqlite3.Connection, session_id: str, new_parent: str, new_child: str) -> bool:
    """Return True if adding edge new_parent→new_child would create a cycle.

    Strategy: if new_child can already reach new_parent via existing forward
    edges, then adding new_parent→new_child would close a cycle.
    Single forward-DFS from new_child; self-reference handled upfront.
    """
    if new_parent == new_child:
        return True

    rows = conn.execute(
        "SELECT parent, child FROM edges WHERE session_id=?", (session_id,)
    ).fetchall()
    forward: dict[str, list[str]] = {}
    for row in rows:
        forward.setdefault(row["parent"], []).append(row["child"])

    # DFS: can we reach new_parent starting from new_child?
    visited: set[str] = set()
    stack = [new_child]
    while stack:
        node = stack.pop()
        if node == new_parent:
            return True
        if node in visited:
            continue
        visited.add(node)
        stack.extend(forward.get(node, []))

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

def call_dag_thinking(
    *,
    db_path: str = _DEFAULT_DB,
    action: str,
    session_id: str,
    node_name: str | None = None,
    thought_type: str | None = None,
    payload: str | None = None,
    depends_on: list[str] | None = None,
    note: str = "",
    target_node: str | None = None,
    reason: str = "",
    ccr_hash: str | None = None,
) -> dict:
    if not session_id or not session_id.strip():
        raise ValueError("session_id cannot be empty or blank")

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

# I07: 세션 컨텍스트 압박 경보 임계값 (노드 수 기반)
_PRESSURE_MEDIUM = 8   # 이 수 이상이면 "medium" 경보
_PRESSURE_HIGH   = 15  # 이 수 이상이면 "high" 경보


def _compute_context_pressure(conn: sqlite3.Connection, session_id: str) -> dict:
    """I07: 세션 COMPLETED 노드 수 기반 컨텍스트 압박 수준 계산 (upsert 후 호출)."""
    node_count = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE session_id=? AND status='COMPLETED'", (session_id,)
    ).fetchone()[0]

    if node_count >= _PRESSURE_HIGH:
        level = "high"
        hint = (
            f"Session has {node_count} nodes — approaching reasoning capacity. "
            "Consolidate with a Synthesis node or call status() to close."
        )
    elif node_count >= _PRESSURE_MEDIUM:
        level = "medium"
        hint = (
            f"Session has {node_count} nodes. "
            "Consider moving toward Synthesis to converge findings."
        )
    else:
        level = "low"
        hint = f"Session has {node_count} node(s). Plenty of capacity for further reasoning."

    return {"level": level, "node_count": node_count, "hint": hint}


def _compute_dag_health(node_rows, edge_rows) -> dict:
    """I08: DAG 수렴 상태·고립 노드·최장 체인 깊이 진단."""
    if not node_rows:
        return {
            "is_converging": False,
            "max_depth": 0,
            "orphan_nodes": [],
            "thought_type_distribution": {},
            "health_hint": "No nodes yet. Start with an Objective node.",
        }

    node_names = {r["name"] for r in node_rows}
    type_dist: dict[str, int] = {}
    is_converging = False

    for r in node_rows:
        if r["status"] != "COMPLETED":
            continue
        t = r["thought_type"]
        type_dist[t] = type_dist.get(t, 0) + 1
        if t in ("Synthesis", "Action"):
            is_converging = True

    # 엣지 정보로 연결성 분석
    child_map: dict[str, list[str]] = {}
    has_parent: set[str] = set()
    has_child: set[str] = set()
    for r in edge_rows:
        child_map.setdefault(r["parent"], []).append(r["child"])
        has_parent.add(r["child"])
        has_child.add(r["parent"])

    # 고립 노드: 2개 이상 노드 세션에서 엣지가 전혀 없는 노드
    connected = has_parent | has_child
    orphan_nodes = (
        sorted(n for n in node_names if n not in connected)
        if len(node_names) > 1 else []
    )

    # 최장 체인 깊이: 루트 노드(부모 없음)에서 BFS
    roots = [n for n in node_names if n not in has_parent]
    max_depth = 0
    if roots:
        bfs: deque[tuple[str, int]] = deque((r, 0) for r in roots)
        visited: set[str] = set()
        while bfs:
            node, depth = bfs.popleft()
            if node in visited:
                continue
            visited.add(node)
            if depth > max_depth:
                max_depth = depth
            for child in child_map.get(node, []):
                if child not in visited:
                    bfs.append((child, depth + 1))

    # health_hint: 우선순위 — 고립 > 수렴 > 미수렴 경고 > 정상
    total_nodes = len(node_names)
    if orphan_nodes:
        health_hint = (
            f"Orphan node(s) detected: {orphan_nodes}. "
            "Use depends_on to connect them to the reasoning chain."
        )
    elif is_converging:
        health_hint = (
            "DAG converging — Synthesis or Action node reached. "
            "Consider closing the session or adding Action nodes."
        )
    elif total_nodes >= 5 and "Synthesis" not in type_dist and "Action" not in type_dist:
        health_hint = (
            f"{total_nodes} nodes without Synthesis — "
            "consider adding a Synthesis node to consolidate findings."
        )
    else:
        health_hint = "Reasoning in progress. Continue building toward Synthesis."

    return {
        "is_converging": is_converging,
        "max_depth": max_depth,
        "orphan_nodes": orphan_nodes,
        "thought_type_distribution": type_dist,
        "health_hint": health_hint,
    }

# I05: thought_type별 컨텍스트 힌트 (LLM 다음 단계 안내)
_NEXT_HINTS: dict[str, str] = {
    "Objective":   "Add Hypothesis or Assumption nodes to explore this objective.",
    "Hypothesis":  "Add Evidence or Assumption nodes to support or challenge this hypothesis.",
    "Assumption":  "Add Evidence to validate, or Critique to challenge this assumption.",
    "Evidence":    "Add Synthesis to draw conclusions, or Critique to challenge the evidence.",
    "Critique":    "Add Synthesis to reconcile findings, or revise the critiqued node.",
    "Synthesis":   "Add Action nodes to operationalize insights, or call status() to close.",
    "Action":      "All conclusions reached. Call status() to review the full DAG.",
}


def _action_think(
    *,
    db_path: str,
    session_id: str,
    node_name: str | None,
    thought_type: str | None,
    payload: str | None,
    depends_on: list[str],
    note: str,
) -> dict:
    # --- validation ---
    if not node_name or not node_name.strip():
        raise ValueError("node_name is required for action='think' and cannot be blank")
    if not thought_type or thought_type not in VALID_THOUGHT_TYPES:
        raise ValueError(f"thought_type must be one of: {sorted(VALID_THOUGHT_TYPES)}")
    if not payload:
        raise ValueError("payload is required for action='think'")
    if len(payload) < 80:
        raise ValueError("payload must be at least 80 characters")
    if len(payload) > 1500:
        raise ValueError("payload must be at most 1500 characters")

    with contextlib.closing(_db(db_path)) as conn:
        with conn:
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
            parent_context: dict = {}
            found: dict[str, sqlite3.Row] = (
                {
                    r["name"]: r
                    for r in conn.execute(
                        "SELECT name, thought_type, payload, compressed, ccr_hash, status "
                        "FROM nodes WHERE session_id=? AND name IN "
                        f"({','.join(['?'] * len(depends_on))})",
                        (session_id, *depends_on),
                    ).fetchall()
                }
                if depends_on
                else {}
            )

            for parent_name in depends_on:
                row = found.get(parent_name)
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
                    entry["warning"] = (
                        f"Parent node '{parent_name}' is INVALIDATED"
                        " — review before proceeding"
                    )
                    entry["is_invalidated"] = True

                parent_context[parent_name] = entry

            # --- compress payload (I06: thought_type 전달) ---
            compressed_text, hash_val, tokens_saved = compress(payload, thought_type)
            is_compressed = compressed_text != payload

            # --- upsert node ---
            existing = conn.execute(
                "SELECT id, ccr_hash, payload, compressed "
                "FROM nodes WHERE session_id=? AND name=?",
                (session_id, node_name),
            ).fetchone()

            if existing:
                old_ccr_hash = existing["ccr_hash"]
                # Compute old contribution to subtract before adding new value (BUG-1 fix)
                old_orig = estimate_tokens(existing["payload"])
                old_comp = (
                    estimate_tokens(existing["compressed"])
                    if existing["compressed"]
                    else old_orig
                )
                old_contribution = old_orig - old_comp

                # stale outgoing edges from previous version are no longer valid
                conn.execute(
                    "DELETE FROM edges WHERE session_id=? AND parent=?",
                    (session_id, node_name),
                )

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

                if old_ccr_hash != hash_val:
                    conn.execute("DELETE FROM ccr_store WHERE hash=?", (old_ccr_hash,))
            else:
                old_contribution = 0
                conn.execute(
                    """INSERT INTO nodes
                       (session_id, name, thought_type, payload, compressed,
                        ccr_hash, note, status)
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
                if parent in found:
                    conn.execute(
                        "INSERT OR IGNORE INTO edges (session_id, parent, child) VALUES (?,?,?)",
                        (session_id, parent, node_name),
                    )

            # --- update session aggregate (net delta only — avoids double-count on update) ---
            delta = tokens_saved - old_contribution
            conn.execute(
                "UPDATE sessions SET tokens_saved = tokens_saved + ? WHERE id=?",
                (delta, session_id),
            )

            # I02: read back session cumulative total after update
            session_row = conn.execute(
                "SELECT tokens_saved FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
            session_total_saved = session_row["tokens_saved"] if session_row else tokens_saved

            # I07: 컨텍스트 압박 수준 (upsert 후 — 동일 트랜잭션 내 COUNT 반영)
            context_pressure = _compute_context_pressure(conn, session_id)

    result: dict = {
        "status": op_status,
        "node": node_name,
        "ccr_hash": hash_val,
        "compression": {
            "tokens_saved": tokens_saved,
            "session_total_saved": session_total_saved,  # I02: PLAN.md 명세 준수
        },
        "next_hint": _NEXT_HINTS.get(thought_type, "Call status() to review DAG."),  # I05
        "context_pressure": context_pressure,  # I07: 사전 예방적 컨텍스트 압박 경보
    }

    if parent_context:
        result["parent_context"] = parent_context

    return result


# ---------------------------------------------------------------------------
# action="status"
# ---------------------------------------------------------------------------

def _action_status(*, db_path: str, session_id: str) -> dict:
    with contextlib.closing(_db(db_path)) as conn:
        with conn:
            _ensure_session(conn, session_id)

            node_rows = conn.execute(
                "SELECT name, thought_type, ccr_hash, status, created_at, payload, compressed "
                "FROM nodes WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()

            edge_rows = conn.execute(
                "SELECT parent, child FROM edges WHERE session_id=?",
                (session_id,),
            ).fetchall()

            session_row = conn.execute(
                "SELECT tokens_saved FROM sessions WHERE id=?",
                (session_id,),
            ).fetchone()

    # I08: DAG 수렴 상태 진단 (DB 연결 닫힌 후 — 이미 fetch된 Row 객체로 계산)
    dag_health = _compute_dag_health(node_rows, edge_rows)

    completed_rows = [r for r in node_rows if r["status"] == "COMPLETED"]
    tokens_original = sum(estimate_tokens(r["payload"]) for r in completed_rows)
    tokens_compressed = sum(
        estimate_tokens(r["compressed"]) if r["compressed"] else estimate_tokens(r["payload"])
        for r in completed_rows
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
                f"dag_thinking(action='restore', "
                f"session_id={repr(session_id)}, "
                f"ccr_hash={repr(row['ccr_hash'])})"
            ),
        })

    return {
        "session_id": session_id,
        "dag": {
            "nodes": [
                {
                    "name": r["name"],
                    "thought_type": r["thought_type"],
                    "status": r["status"],
                    "created_at": r["created_at"],  # I04
                }
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
                "dag_thinking(action='restore', session_id='<id>', ccr_hash='<hash>')"
            ),
            "nodes": manifest_nodes,
        },
        "dag_health": dag_health,  # I08: 수렴 상태 진단
    }


# ---------------------------------------------------------------------------
# action="invalidate"
# ---------------------------------------------------------------------------

def _action_invalidate(
    *, db_path: str, session_id: str, target_node: str | None, reason: str
) -> dict:
    if not target_node:
        raise ValueError("target_node is required for action='invalidate'")

    with contextlib.closing(_db(db_path)) as conn:
        with conn:
            _ensure_session(conn, session_id)

            # I03: target_node 존재 여부 검증
            exists = conn.execute(
                "SELECT id FROM nodes WHERE session_id=? AND name=?",
                (session_id, target_node),
            ).fetchone()
            if exists is None:
                raise ValueError(
                    f"Node '{target_node}' not found in session '{session_id}'. "
                    "Use action='status' to see available nodes."
                )

            affected = _cascade_invalidate(conn, session_id, target_node)

    return {
        "invalidated": affected,
        "reason": reason,
        "hint": "Re-create with corrected analysis.",
    }


# ---------------------------------------------------------------------------
# action="restore"
# ---------------------------------------------------------------------------

def _action_restore(
    *, db_path: str, session_id: str, ccr_hash_val: str | None
) -> dict:
    with contextlib.closing(_db(db_path)) as conn:
        with conn:
            _ensure_session(conn, session_id)

            if ccr_hash_val is None:
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
                                f"dag_thinking(action='restore', "
                                f"session_id={repr(session_id)}, "
                                f"ccr_hash={repr(r['ccr_hash'])})"
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
            result: dict = {
                "node_name": row["node_name"],
                "original_payload": row["original"],
                "tokens": tokens,
            }

            node = conn.execute(
                "SELECT status FROM nodes WHERE session_id=? AND name=?",
                (session_id, row["node_name"]),
            ).fetchone()
            if node and node["status"] == "INVALIDATED":
                result["warning"] = (
                    f"Node '{row['node_name']}' is INVALIDATED. "
                    "This payload may be stale or superseded."
                )

            return result


# ---------------------------------------------------------------------------
# FastMCP tool — C01: exactly one tool exposed
# ---------------------------------------------------------------------------

mcp = FastMCP("dag-thinking")


@mcp.tool()
def dag_thinking(
    action: Literal["think", "status", "invalidate", "restore"],
    session_id: str,
    node_name: str | None = None,
    thought_type: Literal[
        "Objective", "Hypothesis", "Assumption",
        "Evidence", "Critique", "Synthesis", "Action"
    ] | None = None,
    payload: str | None = None,
    depends_on: list[str] | None = None,
    note: str = "",
    target_node: str | None = None,
    reason: str = "",
    ccr_hash: str | None = None,
) -> dict:
    """
    Single entry point for DAG-structured reasoning with automatic CCR context compression.

    action="think"      — create/update a reasoning node (node_name, thought_type, payload required)
    action="status"     — show DAG topology, metrics, and restoration manifest
    action="invalidate" — cascade-invalidate a node and its descendants (target_node required)
    action="restore"    — retrieve original payload by ccr_hash;
                          omit hash to list all restorable nodes
    """
    return call_dag_thinking(
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
    init_db()
    mcp.run()


if __name__ == "__main__":
    main()
