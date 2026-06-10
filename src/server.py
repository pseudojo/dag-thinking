"""
dag-thinking MCP server — single tool, single entry point.
"""

import contextlib
import os
import sqlite3
from collections import deque
from typing import Literal

from fastmcp import FastMCP

try:
    from .compressor import compress, estimate_tokens
except ImportError:
    from src.compressor import compress, estimate_tokens  # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# DB path — default next to this file, overridable for tests
# ---------------------------------------------------------------------------

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "dag_thinking.db")


# ---------------------------------------------------------------------------
# T01: init_db — 4 tables, WAL mode
# ---------------------------------------------------------------------------


def init_db(path: str = _DEFAULT_DB) -> None:
    with contextlib.closing(_db(path)) as conn:
        # WAL PRAGMA must run outside a transaction
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


# ---------------------------------------------------------------------------
# T02: _db — connection helper with row_factory and busy_timeout
# ---------------------------------------------------------------------------


def _db(path: str = _DEFAULT_DB) -> sqlite3.Connection:
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
# Q-2: _load_forward_edges / _has_cycle_graph — batch edge fetch (1회 조회)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Module-level constants — defined before first use
# ---------------------------------------------------------------------------

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

# I17: depends_on 상한 — SQLite 바인딩 파라미터 제한(999) 안전 마진
_MAX_DEPENDS_ON = 20

# I22: node_name 길이 상한 — DoS 방어 및 SQL 인덱스 효율
_MAX_NODE_NAME_LEN = 200

# I30: session_id 길이 상한 — node_name과 동일 기준
_MAX_SESSION_ID_LEN = 200

# I36: note 길이 상한 — 비압축 scratchpad 무제한 입력 방어
_MAX_NOTE_LEN = 500

# I07: 세션 컨텍스트 압박 경보 임계값 (노드 수 기반)
_PRESSURE_MEDIUM = 8  # 이 수 이상이면 "medium" 경보
_PRESSURE_HIGH = 15  # 이 수 이상이면 "high" 경보

# I05: thought_type별 컨텍스트 힌트 (LLM 다음 단계 안내)
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
# Q-3: _validate_think_inputs — 입력 유효성 검사 (SRP 분리)
# ---------------------------------------------------------------------------


def _validate_think_inputs(
    node_name: str | None,
    thought_type: str | None,
    payload: str | None,
    depends_on: list[str] | None = None,
    note: str | None = "",
) -> None:
    """action='think' 입력 유효성 검사. 실패 시 ValueError 즉시 raise."""
    # I46: note=None(JSON null) 방어 — 빈 문자열로 정규화
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
    # I36: note 길이 상한 — 비압축 scratchpad DoS 방어
    if len(note) > _MAX_NOTE_LEN:
        raise ValueError(
            f"note exceeds maximum length of {_MAX_NOTE_LEN} characters (got {len(note)})"
        )


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
# _resolve_parent_context — depends_on 부모 노드 컨텍스트 해결 (SRP 분리)
# ---------------------------------------------------------------------------


def _resolve_parent_context(
    conn: sqlite3.Connection,
    session_id: str,
    depends_on: list[str],
) -> dict[str, dict]:
    """R-4: 부모 노드 컨텍스트 해결 — _action_think에서 추출 (SRP)."""
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
    if len(session_id) > _MAX_SESSION_ID_LEN:
        raise ValueError(
            f"session_id exceeds maximum length of {_MAX_SESSION_ID_LEN} characters "
            f"(got {len(session_id)})"
        )

    # I29: depends_on 중복 항목 순서 보존 제거 — 불필요한 중복 엣지/사이클감지 방지
    deduped_depends_on = list(dict.fromkeys(depends_on)) if depends_on else []

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
            f"Unknown action: '{action}'. Must be one of: think, status, invalidate, restore"
        )


# ---------------------------------------------------------------------------
# action="think"
# ---------------------------------------------------------------------------


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


def _compute_dag_health(
    node_rows: list[sqlite3.Row],
    edge_rows: list[sqlite3.Row],
) -> dict:
    """I08: DAG 수렴 상태·고립 노드·최장 체인 깊이 진단."""
    if not node_rows:
        return {
            "is_converging": False,
            "max_depth": 0,
            "orphan_nodes": [],
            "thought_type_distribution": {},
            "health_hint": "No nodes yet. Start with an Objective node.",
            "total_nodes": 0,  # I45: COMPLETED 노드 수 (빈 세션)
        }

    # COMPLETED 노드만 구조 분석 대상 (INVALIDATED 제외)
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

    # I10: COMPLETED 전용 서브그래프만 사용 — INVALIDATED 경유 경로 오염 버그 수정
    child_map: dict[str, list[str]] = {}
    has_parent: set[str] = set()
    has_child: set[str] = set()
    for r in edge_rows:
        if r["parent"] in completed_names and r["child"] in completed_names:
            child_map.setdefault(r["parent"], []).append(r["child"])
            has_parent.add(r["child"])
            has_child.add(r["parent"])

    # 고립 노드: COMPLETED 노드 중 엣지가 없는 노드 (2개 이상일 때만)
    connected = has_parent | has_child
    orphan_nodes = (
        sorted(n for n in completed_names if n not in connected) if len(completed_names) > 1 else []
    )

    # 최장 체인 깊이: COMPLETED 루트 노드(부모 없음)에서 BFS
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

    # health_hint: 우선순위 — 고립 > 수렴 > 미수렴 경고 > 정상
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
        "total_nodes": len(completed_names),  # I45: COMPLETED 노드 수
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
    # Q-3: 입력 유효성 검사 — 분리된 순수 함수로 위임 (I36: note 전달)
    _validate_think_inputs(node_name, thought_type, payload, depends_on, note)

    # PERF-1: CPU 연산을 DB 락 획득 전에 선실행 (SHA-256 + 문장 스코어링)
    tokens_original_val = estimate_tokens(payload)
    compressed_text, hash_val, tokens_saved = compress(payload, thought_type)
    is_compressed = compressed_text != payload

    with contextlib.closing(_db(db_path)) as conn:
        # I20: PERF-2 — session total을 쓰기 트랜잭션 이전에 읽어 SELECT를 락 밖으로 이동
        prev_row = conn.execute(
            "SELECT tokens_saved FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        prev_session_total = prev_row["tokens_saved"] if prev_row else 0
        delta = 0  # with conn: 내에서 갱신됨

        # I40: depends_on 빈 경우 DB 조회·사이클 검사 스킵 (불필요한 full-scan 방지)
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

        with conn:
            _ensure_session(conn, session_id)

            # --- upsert node ---
            existing = conn.execute(
                "SELECT id, ccr_hash, tokens_saved FROM nodes WHERE session_id=? AND name=?",
                (session_id, node_name),
            ).fetchone()

            if existing:
                # Q-1: delta = new_saved - old_saved (이전 공식은 old_compressed를 빼던 버그)
                old_tokens_saved = existing["tokens_saved"]

                # R-EDGE: child=? 로 이 노드의 incoming edges(부모 관계)만 초기화
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

            # R-CCR: OR IGNORE — 복합 PK(hash, session_id)로 세션별 독립 보존
            conn.execute(
                """INSERT OR IGNORE INTO ccr_store (hash, session_id, node_name, original)
                   VALUES (?,?,?,?)""",
                (hash_val, session_id, node_name, payload),
            )

            # I34: executemany 1회 + .get("error") is None 가드 명확화
            valid_parents = [
                p for p in depends_on if parent_context.get(p, {}).get("error") is None
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO edges (session_id, parent, child) VALUES (?,?,?)",
                [(session_id, p, node_name) for p in valid_parents],
            )

            # Q-1: delta = 새 savings - 이전 savings (SUM(tokens_saved) 누적 정확성)
            delta = tokens_saved - old_tokens_saved
            conn.execute(
                "UPDATE sessions SET tokens_saved = tokens_saved + ? WHERE id=?",
                (delta, session_id),
            )
            # I20: SELECT 제거 — session_total_saved는 with conn: 이후 로컬 계산

        # I20: PERF-2 완성 — prev + delta 로컬 계산 (SELECT 없음)
        session_total_saved = prev_session_total + delta

        # I09: PERF-2 완성 — context_pressure COUNT 쿼리를 with conn: 밖으로 이동
        context_pressure = _compute_context_pressure(conn, session_id)

    result: dict = {
        "status": op_status,
        "node": node_name,
        "thought_type": thought_type,  # I42: 생성 결과 확인을 위한 타입 필드
        "ccr_hash": hash_val,
        "compression": {
            "tokens_saved": tokens_saved,
            "session_total_saved": session_total_saved,
        },
        "next_hint": _NEXT_HINTS[thought_type],  # Q-5: thought_type 검증 완료 — dead fallback 제거
        "context_pressure": context_pressure,
    }

    if parent_context:
        result["parent_context"] = parent_context

    return result


# ---------------------------------------------------------------------------
# action="status"
# ---------------------------------------------------------------------------


def _action_status(*, db_path: str, session_id: str) -> dict:
    with contextlib.closing(_db(db_path)) as conn:
        # PERF-2: _ensure_session 쓰기만 트랜잭션 — 읽기 쿼리는 트랜잭션 밖
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

        # R-3: SQL SUM으로 메트릭 계산 — payload 텍스트 로딩 불필요
        metrics_row = conn.execute(
            "SELECT COALESCE(SUM(tokens_original), 0) AS orig, "
            "       COALESCE(SUM(tokens_saved), 0)    AS saved "
            "FROM nodes WHERE session_id=? AND status='COMPLETED'",
            (session_id,),
        ).fetchone()

    # I08: DAG 수렴 상태 진단 (DB 연결 닫힌 후 — 이미 fetch된 Row 객체로 계산)
    dag_health = _compute_dag_health(node_rows, edge_rows)

    tokens_original = metrics_row["orig"]
    tokens_saved_val = metrics_row["saved"]
    tokens_compressed = tokens_original - tokens_saved_val
    ratio = (1 - tokens_compressed / tokens_original) if tokens_original > 0 else 0.0

    # restoration manifest
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
                    "created_at": r["created_at"],  # I04
                    "ccr_hash": r["ccr_hash"],  # I43: 복원 해시 직접 접근
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
        "dag_health": dag_health,  # I08: 수렴 상태 진단
    }


# ---------------------------------------------------------------------------
# action="invalidate"
# ---------------------------------------------------------------------------


def _action_invalidate(
    *, db_path: str, session_id: str, target_node: str | None, reason: str
) -> dict:
    # I47: strip 후 재할당 — 공백 포함 이름이 DB 조회를 미스하는 버그 수정
    if target_node:
        target_node = target_node.strip()
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


def _action_restore(*, db_path: str, session_id: str, ccr_hash_val: str | None) -> dict:
    with contextlib.closing(_db(db_path)) as conn:
        # PERF-2: _ensure_session 쓰기만 트랜잭션 — 읽기 쿼리는 트랜잭션 밖
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

        # I28: C18 session scoping + nodes status — LEFT JOIN으로 1-query 통합
        row = conn.execute(
            "SELECT c.node_name, c.original, n.status "
            "FROM ccr_store c "
            "LEFT JOIN nodes n ON n.session_id=c.session_id AND n.name=c.node_name "
            "WHERE c.hash=? AND c.session_id=?",
            (ccr_hash_val, session_id),
        ).fetchone()

        if row is None:
            # SEC-1: 타 세션 존재 여부를 probe하지 않음 — session_id 노출 방지
            raise ValueError(f"Hash '{ccr_hash_val}' not found in session '{session_id}'")

        tokens = estimate_tokens(row["original"])
        result: dict = {
            "node_name": row["node_name"],
            "original_payload": row["original"],
            "tokens": tokens,
        }

        if row["status"] == "INVALIDATED":
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
        "Objective", "Hypothesis", "Assumption", "Evidence", "Critique", "Synthesis", "Action"
    ]
    | None = None,
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
