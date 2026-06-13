"""dag-thinking business logic — status, invalidate, restore, info, dispatcher."""

import contextlib
import importlib.metadata
import os
import sqlite3
from collections import deque
from typing import TypedDict

from .compressor import estimate_tokens
from .db import (
    _DEFAULT_DB,
    _cascade_invalidate,
    _db,
    _ensure_session,
)
from .think import _action_think

class StatusResult(TypedDict):
    session_id: str
    dag: dict
    metrics: dict
    restoration_manifest: dict
    dag_health: dict


class InvalidateResult(TypedDict):
    invalidated: list[str]
    reason: str
    hint: str


class RestoreListResult(TypedDict):
    restorable_nodes: list[dict]


class RestorePayloadResult(TypedDict, total=False):
    node_name: str
    original_payload: str
    tokens: int
    warning: str


class InfoResult(TypedDict):
    server: str
    version: str
    db_path: str
    db_exists: bool
    actions: list[str]
    status: str


_MAX_SESSION_ID_LEN = 200


# ---------------------------------------------------------------------------
# DAG health analysis (moved from think.py — used only by _action_status)
# ---------------------------------------------------------------------------


def _compute_dag_health(
    node_rows: list[sqlite3.Row],
    edge_rows: list[sqlite3.Row],
) -> dict:
    if not node_rows:
        return {
            "is_converging": False,
            "max_depth": 0,
            "orphan_nodes": [],
            "thought_type_distribution": {},
            "health_hint": "No nodes yet. Start with an Objective node.",
            "total_nodes": 0,
        }

    completed_names = {r["name"] for r in node_rows if r["status"] == "COMPLETED"}
    type_dist: dict[str, int] = {}
    is_converging = False

    for r in node_rows:
        if r["status"] != "COMPLETED":
            continue
        t = r["thought_type"]
        type_dist[t] = type_dist.get(t, 0) + 1
        if t in ("Synthesis", "Action"):
            is_converging = True

    child_map: dict[str, list[str]] = {}
    has_parent: set[str] = set()
    has_child: set[str] = set()
    for r in edge_rows:
        if r["parent"] in completed_names and r["child"] in completed_names:
            child_map.setdefault(r["parent"], []).append(r["child"])
            has_parent.add(r["child"])
            has_child.add(r["parent"])

    connected = has_parent | has_child
    orphan_nodes = (
        sorted(n for n in completed_names if n not in connected) if len(completed_names) > 1 else []
    )

    roots = [n for n in completed_names if n not in has_parent]
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

    total_nodes = len(completed_names)
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
        "total_nodes": total_nodes,
    }


# ---------------------------------------------------------------------------
# action="status"
# ---------------------------------------------------------------------------


def _action_status(*, db_path: str, session_id: str) -> StatusResult:
    with contextlib.closing(_db(db_path)) as conn:
        with conn:
            _ensure_session(conn, session_id)

        node_rows = conn.execute(
            "SELECT name, thought_type, ccr_hash, status, created_at "
            "FROM nodes WHERE session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()

        edge_rows = conn.execute(
            "SELECT parent, child FROM edges WHERE session_id=?",
            (session_id,),
        ).fetchall()

        metrics_row = conn.execute(
            "SELECT COALESCE(SUM(tokens_original), 0) AS orig, "
            "       COALESCE(SUM(tokens_saved), 0)    AS saved "
            "FROM nodes WHERE session_id=? AND status='COMPLETED'",
            (session_id,),
        ).fetchone()

    dag_health = _compute_dag_health(node_rows, edge_rows)

    tokens_original = metrics_row["orig"]
    tokens_saved_val = metrics_row["saved"]
    tokens_compressed = tokens_original - tokens_saved_val
    ratio = (1 - tokens_compressed / tokens_original) if tokens_original > 0 else 0.0

    manifest_nodes = []
    for row in node_rows:
        manifest_nodes.append(
            {
                "name": row["name"],
                "type": row["thought_type"],
                "status": row["status"],
                "ccr_hash": row["ccr_hash"],
                "restore_cmd": (
                    f"dag_thinking(action='restore', "
                    f"session_id={repr(session_id)}, "
                    f"ccr_hash={repr(row['ccr_hash'])})"
                ),
            }
        )

    return {
        "session_id": session_id,
        "dag": {
            "nodes": [
                {
                    "name": r["name"],
                    "thought_type": r["thought_type"],
                    "status": r["status"],
                    "created_at": r["created_at"],
                    "ccr_hash": r["ccr_hash"],
                }
                for r in node_rows
            ],
            "edges": [{"parent": r["parent"], "child": r["child"]} for r in edge_rows],
        },
        "metrics": {
            "tokens_original": tokens_original,
            "tokens_compressed": tokens_compressed,
            "tokens_saved": tokens_saved_val,
            "ratio": round(ratio, 4),
        },
        "restoration_manifest": {
            "how_to_restore": (
                "dag_thinking(action='restore', session_id='<id>', ccr_hash='<hash>')"
            ),
            "nodes": manifest_nodes,
        },
        "dag_health": dag_health,
    }


# ---------------------------------------------------------------------------
# action="invalidate"
# ---------------------------------------------------------------------------


def _action_invalidate(
    *, db_path: str, session_id: str, target_node: str | None, reason: str
) -> InvalidateResult:
    if target_node:
        target_node = target_node.strip()
    if not target_node:
        raise ValueError("target_node is required for action='invalidate'")

    with contextlib.closing(_db(db_path)) as conn:
        with conn:
            _ensure_session(conn, session_id)

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
) -> RestoreListResult | RestorePayloadResult:
    with contextlib.closing(_db(db_path)) as conn:
        with conn:
            _ensure_session(conn, session_id)

        if ccr_hash_val is None:
            rows = conn.execute(
                "SELECT name, ccr_hash, status FROM nodes WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
            return {
                "restorable_nodes": [
                    {
                        "name": r["name"],
                        "ccr_hash": r["ccr_hash"],
                        "status": r["status"],
                        "restore_cmd": (
                            f"dag_thinking(action='restore', "
                            f"session_id={repr(session_id)}, "
                            f"ccr_hash={repr(r['ccr_hash'])})"
                        ),
                    }
                    for r in rows
                ]
            }

        row = conn.execute(
            "SELECT c.node_name, c.original, n.status "
            "FROM ccr_store c "
            "LEFT JOIN nodes n ON n.session_id=c.session_id AND n.name=c.node_name "
            "WHERE c.hash=? AND c.session_id=?",
            (ccr_hash_val, session_id),
        ).fetchone()

        if row is None:
            raise ValueError(f"Hash '{ccr_hash_val}' not found in session '{session_id}'")

        tokens = estimate_tokens(row["original"])
        result: dict = {
            "node_name": row["node_name"],
            "original_payload": row["original"],
            "tokens": tokens,
        }

        if row["status"] is None:
            result["warning"] = (
                f"Node '{row['node_name']}' was deleted. "
                "This payload is from a node that no longer exists in the session."
            )
        elif row["status"] == "INVALIDATED":
            result["warning"] = (
                f"Node '{row['node_name']}' is INVALIDATED. "
                "This payload may be stale or superseded."
            )

        return result


# ---------------------------------------------------------------------------
# action="info" — §3.2 diagnostic endpoint
# ---------------------------------------------------------------------------


def _action_info(*, db_path: str) -> InfoResult:
    """MCP Best Practices §3.2 — lightweight server diagnostic."""
    try:
        version = importlib.metadata.version("dag-thinking")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"
    return {
        "server": "dag_thinking_mcp",
        "version": version,
        "db_path": str(db_path),
        "db_exists": bool(os.path.exists(db_path)),
        "actions": ["think", "status", "invalidate", "restore", "info"],
        "status": "ready",
    }


# ---------------------------------------------------------------------------
# Public dispatcher
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
    if action == "info":
        return _action_info(db_path=db_path)

    if not session_id or not session_id.strip():
        raise ValueError("session_id cannot be empty or blank")
    if len(session_id) > _MAX_SESSION_ID_LEN:
        raise ValueError(
            f"session_id exceeds maximum length of {_MAX_SESSION_ID_LEN} characters "
            f"(got {len(session_id)})"
        )

    if node_name is not None:
        node_name = node_name.strip()

    deduped_depends_on = (
        list(dict.fromkeys(p.strip() for p in depends_on if p.strip())) if depends_on else []
    )

    if action == "think":
        return _action_think(
            db_path=db_path,
            session_id=session_id,
            node_name=node_name,
            thought_type=thought_type,
            payload=payload,
            depends_on=deduped_depends_on,
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
            f"Unknown action: '{action}'. Must be one of: think, status, invalidate, restore, info"
        )
