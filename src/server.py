"""dag-thinking MCP server — thin FastMCP layer, single tool entry point."""

import json
from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from .actions import (
    _PRESSURE_MEDIUM,
    VALID_THOUGHT_TYPES,
    _action_status,
    _compute_dag_health,
    _resolve_parent_context,
    _validate_think_inputs,
    call_dag_thinking,
)
from .db import (
    _DEFAULT_DB,
    _cascade_invalidate,
    _db,
    _ensure_session,
    _has_cycle_graph,
    _load_forward_edges,
    init_db,
)

# Re-export for test backward compatibility
__all__ = [
    "VALID_THOUGHT_TYPES",
    "_PRESSURE_MEDIUM",
    "_cascade_invalidate",
    "_db",
    "_ensure_session",
    "_load_forward_edges",
    "call_dag_thinking",
    "_resolve_parent_context",
    "_has_cycle_graph",
    "_validate_think_inputs",
    "_compute_dag_health",
    "init_db",
    "_DEFAULT_DB",
    "mcp",
    "dag_thinking",
    "get_session_resource",
    "_get_session_resource_data",
]

# ---------------------------------------------------------------------------
# FastMCP server — §2.2 XML semantic tags in instructions
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "dag_thinking_mcp",
    instructions=(
        "<use_case>Use this tool for structured DAG reasoning sessions. "
        "Records reasoning steps as typed nodes (Objective/Hypothesis/Assumption/Evidence/"
        "Critique/Synthesis/Action) connected by dependency edges, with automatic CCR context "
        "compression to reduce token usage across long sessions.</use_case>"
        "<important_notes>"
        "Single tool: dag_thinking(action=...). "
        "Actions: think (create/update node), status (view DAG + metrics), "
        "invalidate (cascade-mark stale nodes), restore (retrieve compressed payload), "
        "info (server diagnostic). "
        "Use action='status' to get ccr_hash values needed for restore. "
        "Use action='info' to verify server configuration."
        "</important_notes>"
    ),
)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@mcp.tool(
    name="dag_thinking",
    annotations={
        "title": "DAG-structured reasoning with CCR compression",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def dag_thinking(
    action: Annotated[
        Literal["think", "status", "invalidate", "restore", "info"],
        Field(
            description=(
                "Operation to perform. "
                "'think': create/update a reasoning node "
                "(requires node_name, thought_type, payload). "
                "'status': view DAG topology, metrics, and restoration manifest. "
                "'invalidate': cascade-mark a node and descendants as INVALIDATED "
                "(requires target_node). "
                "'restore': retrieve original payload by ccr_hash; "
                "omit hash to list all restorable nodes. "
                "'info': server diagnostic — returns version, db_path, available actions."
            )
        ),
    ],
    session_id: Annotated[
        str,
        Field(
            description=(
                "Unique session identifier. Use a consistent ID across all calls "
                "in one reasoning session (e.g. 'analysis_2026_01'). Max 200 chars."
            ),
            min_length=1,
            max_length=200,
        ),
    ] = "",
    node_name: Annotated[
        str | None,
        Field(
            description=(
                "Reasoning node name (required for action='think'). "
                "Must be unique within the session. "
                "Leading/trailing spaces are stripped. Max 200 chars."
            ),
            max_length=200,
        ),
    ] = None,
    thought_type: Annotated[
        Literal[
            "Objective", "Hypothesis", "Assumption", "Evidence", "Critique", "Synthesis", "Action"
        ]
        | None,
        Field(
            description=(
                "Reasoning node type (required for action='think'). "
                "Recommended flow: Objective -> Hypothesis/Assumption -> "
                "Evidence -> Synthesis -> Action. "
                "Use Critique to challenge any node."
            )
        ),
    ] = None,
    payload: Annotated[
        str | None,
        Field(
            description=(
                "Content of this reasoning step (required for action='think'). "
                "80-1500 characters. Long content is automatically compressed and cached via CCR."
            ),
            min_length=80,
            max_length=1500,
        ),
    ] = None,
    depends_on: Annotated[
        list[str] | None,
        Field(
            description=(
                "Parent node names whose context this node builds upon (action='think'). "
                "Parent payloads are auto-resolved into parent_context in the response. "
                "Max 20 parents. Duplicates and surrounding spaces are stripped automatically."
            )
        ),
    ] = None,
    note: Annotated[
        str,
        Field(
            description=(
                "Scratchpad text for this node — not compressed, not indexed. "
                "Use for temporary annotations or reasoning metadata. Max 500 chars."
            ),
            max_length=500,
        ),
    ] = "",
    target_node: Annotated[
        str | None,
        Field(
            description=(
                "Node name to cascade-invalidate (required for action='invalidate'). "
                "All descendant nodes are also marked INVALIDATED. "
                "Use action='status' to see available node names. Max 200 chars."
            ),
            max_length=200,
        ),
    ] = None,
    reason: Annotated[
        str,
        Field(
            description=(
                "Human-readable reason for invalidation (action='invalidate'). "
                "Optional — included in the response for audit trail. Max 500 chars."
            ),
            max_length=500,
        ),
    ] = "",
    ccr_hash: Annotated[
        str | None,
        Field(
            description=(
                "24-char hex hash to restore (action='restore'). "
                "Omit to list all restorable nodes in the session. "
                "Find hashes in the restoration_manifest returned by action='status'."
            )
        ),
    ] = None,
) -> dict:
    """
    Single entry point for DAG-structured reasoning with automatic CCR context compression.

    action="think"      — create/update a reasoning node (node_name, thought_type, payload required)
    action="status"     — show DAG topology, metrics, and restoration manifest
    action="invalidate" — cascade-invalidate a node and its descendants (target_node required)
    action="restore"    — retrieve original payload by ccr_hash (omit hash to list all)
    action="info"       — server diagnostic (version, db_path, available actions)

    Examples:
        - Use when: recording a new reasoning step
          -> action='think', node_name='hypothesis_1', thought_type='Hypothesis', payload='...'
        - Use when: checking session progress or retrieving ccr_hash values for restore
          -> action='status', session_id='my_session'
        - Use when: a hypothesis or assumption is disproven and descendants should be invalidated
          -> action='invalidate', target_node='hypothesis_1'
        - Use when: retrieving the full original text after CCR compression
          -> action='restore', ccr_hash='<hash from status restoration_manifest>'
        - Use when: verifying server configuration or available actions
          -> action='info'
        - Don't use when: you only need simple key-value storage without DAG reasoning structure
    """
    try:
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
    except ValueError as e:
        return {"isError": True, "error": str(e)}


# ---------------------------------------------------------------------------
# MCP Resource — read-only session snapshot
# ---------------------------------------------------------------------------


def _get_session_resource_data(session_id: str, db_path: str = _DEFAULT_DB) -> str:
    """Session state JSON — testable helper for the MCP resource."""
    return json.dumps(_action_status(db_path=db_path, session_id=session_id), indent=2)


@mcp.resource("dag-thinking-session://{session_id}")
def get_session_resource(session_id: str) -> str:
    """Read-only snapshot of a dag-thinking session's DAG state and metrics.

    Use action='status' tool for the full response including restoration manifest.
    """
    return _get_session_resource_data(session_id)


def main():
    init_db()
    mcp.run()


if __name__ == "__main__":
    main()
