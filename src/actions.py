"""dag-thinking business logic — status, invalidate, restore, info, dispatcher."""

import contextlib
import importlib.metadata
import os

from .compressor import estimate_tokens
from .db import (
    _DEFAULT_DB,
    _cascade_invalidate,
    _db,
    _ensure_session,
)
from .think import _action_think, _compute_dag_health

_MAX_SESSION_ID_LEN = 200


# ---------------------------------------------------------------------------
# action="status"
# ---------------------------------------------------------------------------


def _action_status(*, db_path: str, session_id: str) -> dict:
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
) -> dict:
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


def _action_restore(*, db_path: str, session_id: str, ccr_hash_val: str | None) -> dict:
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


def _action_info(*, db_path: str) -> dict:
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
