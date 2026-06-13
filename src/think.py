"""dag-thinking think action — input validation, DAG analysis, node creation."""

import contextlib
import sqlite3
from typing import TypedDict

from .compressor import compress, estimate_tokens
from .db import (
    _db,
    _ensure_session,
    _has_cycle_graph,
    _load_forward_edges,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class ThinkResult(TypedDict, total=False):
    status: str
    node: str
    thought_type: str
    ccr_hash: str
    compression: dict
    next_hint: str
    context_pressure: dict
    parent_context: dict


VALID_THOUGHT_TYPES = frozenset(
    {
        "Objective",
        "Hypothesis",
        "Assumption",
        "Evidence",
        "Critique",
        "Synthesis",
        "Action",
    }
)

_MAX_DEPENDS_ON = 20
_MAX_NODE_NAME_LEN = 200
_MAX_NOTE_LEN = 500
_PRESSURE_MEDIUM = 8
_PRESSURE_HIGH = 15

_NEXT_HINTS: dict[str, str] = {
    "Objective": "Add Hypothesis or Assumption nodes to explore this objective.",
    "Hypothesis": "Add Evidence or Assumption nodes to support or challenge this hypothesis.",
    "Assumption": "Add Evidence to validate, or Critique to challenge this assumption.",
    "Evidence": "Add Synthesis to draw conclusions, or Critique to challenge the evidence.",
    "Critique": "Add Synthesis to reconcile findings, or revise the critiqued node.",
    "Synthesis": "Add Action nodes to operationalize insights, or call status() to close.",
    "Action": "All conclusions reached. Call status() to review the full DAG.",
}


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def _validate_think_inputs(
    node_name: str | None,
    thought_type: str | None,
    payload: str | None,
    depends_on: list[str] | None = None,
    note: str | None = "",
) -> None:
    """action='think' 입력 유효성 검사. 실패 시 ValueError 즉시 raise."""
    if note is None:
        note = ""
    if not node_name or not node_name.strip():
        raise ValueError("node_name is required for action='think' and cannot be blank")
    if len(node_name) > _MAX_NODE_NAME_LEN:
        raise ValueError(
            f"node_name exceeds maximum length of {_MAX_NODE_NAME_LEN} characters "
            f"(got {len(node_name)})"
        )
    if not thought_type or thought_type not in VALID_THOUGHT_TYPES:
        raise ValueError(f"thought_type must be one of: {sorted(VALID_THOUGHT_TYPES)}")
    if not payload or not payload.strip():
        raise ValueError("payload cannot be blank or whitespace-only")
    if len(payload) < 80:
        raise ValueError("payload must be at least 80 characters")
    if len(payload) > 1500:
        raise ValueError("payload must be at most 1500 characters")
    if depends_on is not None and len(depends_on) > _MAX_DEPENDS_ON:
        raise ValueError(
            f"depends_on exceeds maximum of {_MAX_DEPENDS_ON} parents (got {len(depends_on)})"
        )
    if len(note) > _MAX_NOTE_LEN:
        raise ValueError(
            f"note exceeds maximum length of {_MAX_NOTE_LEN} characters (got {len(note)})"
        )


# ---------------------------------------------------------------------------
# Parent context resolver
# ---------------------------------------------------------------------------


def _resolve_parent_context(
    conn: sqlite3.Connection,
    session_id: str,
    depends_on: list[str],
) -> dict[str, dict]:
    if not depends_on:
        return {}

    placeholders = ",".join(["?"] * len(depends_on))
    found: dict[str, sqlite3.Row] = {
        r["name"]: r
        for r in conn.execute(
            f"SELECT name, thought_type, payload, compressed, ccr_hash, status "
            f"FROM nodes WHERE session_id=? AND name IN ({placeholders})",
            (session_id, *depends_on),
        ).fetchall()
    }

    result: dict[str, dict] = {}
    for parent_name in depends_on:
        row = found.get(parent_name)
        if row is None:
            result[parent_name] = {"error": f"Node '{parent_name}' not found"}
            continue

        entry: dict = {
            "thought_type": row["thought_type"],
            "ccr_hash": row["ccr_hash"],
            "is_compressed": row["compressed"] is not None,
            "payload": row["compressed"] if row["compressed"] else row["payload"],
        }
        if row["status"] == "INVALIDATED":
            entry["warning"] = (
                f"Parent node '{parent_name}' is INVALIDATED — review before proceeding"
            )
            entry["is_invalidated"] = True

        result[parent_name] = entry

    return result


# ---------------------------------------------------------------------------
# Context pressure
# ---------------------------------------------------------------------------


def _compute_context_pressure(conn: sqlite3.Connection, session_id: str) -> dict:
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


# ---------------------------------------------------------------------------
# action="think"
# ---------------------------------------------------------------------------


def _action_think(
    *,
    db_path: str,
    session_id: str,
    node_name: str | None,
    thought_type: str | None,
    payload: str | None,
    depends_on: list[str],
    note: str,
) -> ThinkResult:
    _validate_think_inputs(node_name, thought_type, payload, depends_on, note)

    tokens_original_val = estimate_tokens(payload)
    compressed_text, hash_val, tokens_saved = compress(payload, thought_type)
    is_compressed = compressed_text != payload

    with contextlib.closing(_db(db_path)) as conn:
        prev_row = conn.execute(
            "SELECT tokens_saved FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        prev_session_total = prev_row["tokens_saved"] if prev_row else 0

        with conn:
            _ensure_session(conn, session_id)

            if depends_on:
                forward_graph = _load_forward_edges(conn, session_id)
                for parent in depends_on:
                    if _has_cycle_graph(forward_graph, parent, node_name):
                        raise ValueError(
                            f"Cycle detected: adding edge {parent}→{node_name} would create a cycle"
                        )
                parent_context = _resolve_parent_context(conn, session_id, depends_on)
            else:
                parent_context = {}

            existing = conn.execute(
                "SELECT id, ccr_hash, tokens_saved FROM nodes WHERE session_id=? AND name=?",
                (session_id, node_name),
            ).fetchone()

            if existing:
                old_tokens_saved = existing["tokens_saved"]
                conn.execute(
                    "DELETE FROM edges WHERE session_id=? AND child=?",
                    (session_id, node_name),
                )
                conn.execute(
                    """UPDATE nodes
                       SET thought_type=?, payload=?, compressed=?, ccr_hash=?,
                           note=?, status='COMPLETED', created_at=CURRENT_TIMESTAMP,
                           tokens_original=?, tokens_saved=?
                       WHERE session_id=? AND name=?""",
                    (
                        thought_type,
                        payload,
                        compressed_text if is_compressed else None,
                        hash_val,
                        note,
                        tokens_original_val,
                        tokens_saved,
                        session_id,
                        node_name,
                    ),
                )
                op_status = "updated"
            else:
                old_tokens_saved = 0
                conn.execute(
                    """INSERT INTO nodes
                       (session_id, name, thought_type, payload, compressed,
                        ccr_hash, note, status, tokens_original, tokens_saved)
                       VALUES (?,?,?,?,?,?,?,'COMPLETED',?,?)""",
                    (
                        session_id,
                        node_name,
                        thought_type,
                        payload,
                        compressed_text if is_compressed else None,
                        hash_val,
                        note,
                        tokens_original_val,
                        tokens_saved,
                    ),
                )
                op_status = "created"

            conn.execute(
                """INSERT OR IGNORE INTO ccr_store (hash, session_id, node_name, original)
                   VALUES (?,?,?,?)""",
                (hash_val, session_id, node_name, payload),
            )

            valid_parents = [
                p for p in depends_on if parent_context.get(p, {}).get("error") is None
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO edges (session_id, parent, child) VALUES (?,?,?)",
                [(session_id, p, node_name) for p in valid_parents],
            )

            delta = tokens_saved - old_tokens_saved
            conn.execute(
                "UPDATE sessions SET tokens_saved = tokens_saved + ? WHERE id=?",
                (delta, session_id),
            )

        session_total_saved = prev_session_total + delta
        context_pressure = _compute_context_pressure(conn, session_id)

    result: dict = {
        "status": op_status,
        "node": node_name,
        "thought_type": thought_type,
        "ccr_hash": hash_val,
        "compression": {
            "tokens_saved": tokens_saved,
            "session_total_saved": session_total_saved,
        },
        "next_hint": _NEXT_HINTS[thought_type],
        "context_pressure": context_pressure,
    }

    if parent_context:
        result["parent_context"] = parent_context

    return result
