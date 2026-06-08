"""
TDD RED phase tests for P1-2, P1-3, P2-1~P2-6, P3-1
"""

import ast
import contextlib
import sqlite3

import pytest

from tests.helpers import PAYLOAD, invalidate, restore, status, think


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


PAYLOAD2 = (
    "This alternative analysis reveals a different architectural bottleneck in the message broker. "
    "The corrected hypothesis is that vertical scaling addresses the throughput limitation more cost-effectively. "
    "New evidence from load tests shows that connection pooling reduces latency by 70 percent at peak load. "
    "The revised conclusion is to implement connection pooling before considering queue decoupling. "
    "This updated finding must be validated in the staging environment before the next production release."
)


# ---------------------------------------------------------------------------
# P1-2: orphan edge prevention — ghost depends_on skips edge INSERT
# ---------------------------------------------------------------------------

class TestP12OrphanEdgePrevention:

    def test_ghost_parent_creates_no_edge(self, db_path):
        """P1-2: depends_on=['ghost'] (not in DB) → edges table has 0 rows."""
        think(db_path, "s1", "node_a", "Objective", depends_on=["ghost"])
        with contextlib.closing(_conn(db_path)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM edges WHERE session_id='s1'",
            ).fetchone()[0]
        assert count == 0, (
            f"ghost 노드를 parent로 하는 edge가 삽입됨: count={count}"
        )

    def test_valid_parent_still_creates_edge(self, db_path):
        """P1-2 회귀: 유효한 parent → edge 정상 삽입."""
        think(db_path, "s1", "parent_node", "Objective")
        think(db_path, "s1", "child_node", "Hypothesis", depends_on=["parent_node"])
        with contextlib.closing(_conn(db_path)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM edges WHERE session_id='s1' AND parent='parent_node'",
            ).fetchone()[0]
        assert count == 1, "유효한 parent에 대한 edge가 삽입되지 않음"

    def test_mixed_ghost_and_valid_creates_only_valid_edge(self, db_path):
        """P1-2: 유효한 parent와 ghost 혼합 → 유효한 것만 edge 삽입."""
        think(db_path, "s1", "real", "Objective")
        think(db_path, "s1", "child", "Hypothesis", depends_on=["real", "phantom"])
        with contextlib.closing(_conn(db_path)) as conn:
            rows = conn.execute(
                "SELECT parent FROM edges WHERE session_id='s1' AND child='child'",
            ).fetchall()
        parents = {r["parent"] for r in rows}
        assert "real" in parents, "유효한 parent edge 누락"
        assert "phantom" not in parents, "ghost parent edge 삽입됨"


# ---------------------------------------------------------------------------
# P1-3: restore_cmd single-quote escape — must produce valid Python syntax
# ---------------------------------------------------------------------------

class TestP13RestoreCmdEscape:

    def test_session_id_with_quote_valid_syntax_in_status(self, db_path):
        """P1-3: session_id에 single-quote → status restore_cmd가 valid Python."""
        sid = "it's_a_test"
        think(db_path, sid, "node_a", "Objective")
        s = status(db_path, sid)
        manifest_node = s["restoration_manifest"]["nodes"][0]
        cmd = manifest_node["restore_cmd"]
        try:
            ast.parse(cmd, mode="eval")
        except SyntaxError as e:
            pytest.fail(
                f"restore_cmd가 valid Python이 아님 (session_id 내 quote 미처리): "
                f"cmd={cmd!r}, error={e}"
            )

    def test_session_id_with_quote_valid_syntax_in_restore(self, db_path):
        """P1-3: restore(ccr_hash=None) 목록의 restore_cmd도 valid Python."""
        sid = "it's_a_test"
        r = think(db_path, sid, "node_a", "Objective")
        result = restore(db_path, sid)
        cmd = result["restorable_nodes"][0]["restore_cmd"]
        try:
            ast.parse(cmd, mode="eval")
        except SyntaxError as e:
            pytest.fail(
                f"restore_cmd가 valid Python이 아님: cmd={cmd!r}, error={e}"
            )

    def test_node_name_with_quote_valid_syntax(self, db_path):
        """P1-3: ccr_hash는 hex만 포함하므로 이 경로는 주로 session_id 검증."""
        sid = "plain_session"
        think(db_path, sid, "alpha", "Objective")
        s = status(db_path, sid)
        cmd = s["restoration_manifest"]["nodes"][0]["restore_cmd"]
        ast.parse(cmd, mode="eval")  # must not raise


# ---------------------------------------------------------------------------
# P2-1: type_distribution excludes INVALIDATED nodes
# ---------------------------------------------------------------------------

class TestP21TypeDistExcludesInvalidated:

    def test_invalidated_synthesis_not_in_type_dist(self, db_path):
        """P2-1: Synthesis 노드 invalidate 후 type_distribution에 Synthesis 없어야 함."""
        think(db_path, "s1", "obj", "Objective")
        think(db_path, "s1", "syn", "Synthesis", depends_on=["obj"])
        invalidate(db_path, "s1", "syn")
        s = status(db_path, "s1")
        type_dist = s["dag_health"]["thought_type_distribution"]
        assert "Synthesis" not in type_dist, (
            f"INVALIDATED Synthesis가 type_distribution에 포함됨: {type_dist}"
        )

    def test_invalidated_chain_excluded_from_type_dist(self, db_path):
        """P2-1: A→B→C 체인 invalidate 후 type_dist는 빈 dict."""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        think(db_path, "s1", "c", "Evidence", depends_on=["b"])
        invalidate(db_path, "s1", "a")
        s = status(db_path, "s1")
        type_dist = s["dag_health"]["thought_type_distribution"]
        assert type_dist == {}, (
            f"전체 INVALIDATED 세션에서 type_dist가 비어있지 않음: {type_dist}"
        )

    def test_completed_types_still_counted(self, db_path):
        """P2-1 회귀: COMPLETED 노드는 type_dist에 포함."""
        think(db_path, "s1", "obj", "Objective")
        s = status(db_path, "s1")
        type_dist = s["dag_health"]["thought_type_distribution"]
        assert type_dist.get("Objective", 0) == 1, (
            f"COMPLETED Objective가 type_dist에 없음: {type_dist}"
        )


# ---------------------------------------------------------------------------
# P2-2: ccr_store orphan cleanup on node update
# ---------------------------------------------------------------------------

class TestP22CcrStoreOrphanCleanup:

    def test_recreate_node_leaves_one_ccr_entry(self, db_path):
        """P2-2: 노드 재생성 후 ccr_store 엔트리가 1개만 남아야 함."""
        think(db_path, "s1", "node_a", "Objective", payload=PAYLOAD)
        invalidate(db_path, "s1", "node_a")
        think(db_path, "s1", "node_a", "Objective", payload=PAYLOAD2)
        with contextlib.closing(_conn(db_path)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM ccr_store WHERE session_id='s1' AND node_name='node_a'",
            ).fetchone()[0]
        assert count == 1, (
            f"ccr_store에 orphan 엔트리 존재: count={count} (expected 1)"
        )

    def test_same_payload_recreate_still_one_entry(self, db_path):
        """P2-2 회귀: 동일 payload 재생성 시 ccr_store 1개 유지."""
        think(db_path, "s1", "node_a", "Objective", payload=PAYLOAD)
        invalidate(db_path, "s1", "node_a")
        think(db_path, "s1", "node_a", "Objective", payload=PAYLOAD)
        with contextlib.closing(_conn(db_path)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM ccr_store WHERE session_id='s1' AND node_name='node_a'",
            ).fetchone()[0]
        assert count == 1, f"동일 payload 재생성 후 ccr_store count={count}"


# ---------------------------------------------------------------------------
# P2-3: stale edge cleanup on node regeneration
# ---------------------------------------------------------------------------

class TestP23StaleEdgeCleanup:

    def test_recreate_node_removes_old_outgoing_edges(self, db_path):
        """P2-3: A→B 관계에서 A invalidate 후 depends_on=[]로 재생성 → A→B edge 제거."""
        think(db_path, "s1", "node_a", "Objective")
        think(db_path, "s1", "node_b", "Hypothesis", depends_on=["node_a"])
        invalidate(db_path, "s1", "node_a")
        think(db_path, "s1", "node_a", "Objective", payload=PAYLOAD2)  # no depends_on
        with contextlib.closing(_conn(db_path)) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM edges WHERE session_id='s1' AND parent='node_a'",
            ).fetchone()[0]
        assert count == 0, (
            f"재생성 후에도 A→B edge 잔존: count={count}"
        )

    def test_recreate_with_new_depends_on_creates_new_edge(self, db_path):
        """P2-3 회귀: 재생성 시 새 depends_on edge 정상 삽입."""
        think(db_path, "s1", "x", "Objective")
        think(db_path, "s1", "y", "Objective")
        think(db_path, "s1", "z", "Hypothesis", depends_on=["x"])
        invalidate(db_path, "s1", "z")
        think(db_path, "s1", "z", "Hypothesis", depends_on=["y"])
        with contextlib.closing(_conn(db_path)) as conn:
            rows = conn.execute(
                "SELECT parent FROM edges WHERE session_id='s1' AND child='z'",
            ).fetchall()
        parents = {r["parent"] for r in rows}
        assert "y" in parents, "새 depends_on edge 누락"


# ---------------------------------------------------------------------------
# P2-4: status metrics exclude INVALIDATED nodes
# ---------------------------------------------------------------------------

class TestP24StatusMetricsCompletedOnly:

    def test_invalidated_node_excluded_from_tokens(self, db_path):
        """P2-4: 노드 invalidate 후 tokens_original/tokens_compressed가 0."""
        think(db_path, "s1", "node_a", "Objective", payload=PAYLOAD)
        invalidate(db_path, "s1", "node_a")
        s = status(db_path, "s1")
        m = s["metrics"]
        assert m["tokens_original"] == 0, (
            f"INVALIDATED 노드가 tokens_original에 포함됨: {m['tokens_original']}"
        )
        assert m["tokens_compressed"] == 0, (
            f"INVALIDATED 노드가 tokens_compressed에 포함됨: {m['tokens_compressed']}"
        )

    def test_completed_node_still_counted_in_metrics(self, db_path):
        """P2-4 회귀: COMPLETED 노드는 metrics에 포함."""
        think(db_path, "s1", "node_a", "Objective", payload=PAYLOAD)
        s = status(db_path, "s1")
        assert s["metrics"]["tokens_original"] > 0, "COMPLETED 노드가 metrics에 없음"

    def test_partial_invalidation_metrics_only_completed(self, db_path):
        """P2-4: A COMPLETED, B INVALIDATED → metrics는 A만 반영."""
        think(db_path, "s1", "node_a", "Objective", payload=PAYLOAD)
        think(db_path, "s1", "node_b", "Hypothesis", payload=PAYLOAD)
        invalidate(db_path, "s1", "node_b")
        s = status(db_path, "s1")
        # node_a만 COMPLETED, node_b는 INVALIDATED
        # metrics는 node_a 단독 수치여야 함
        from src.compressor import estimate_tokens
        expected = estimate_tokens(PAYLOAD)
        assert s["metrics"]["tokens_original"] == expected, (
            f"metrics tokens_original mismatch: {s['metrics']['tokens_original']} != {expected}"
        )


# ---------------------------------------------------------------------------
# P2-6: session/status composite index
# ---------------------------------------------------------------------------

class TestP26CompositeIndex:

    def test_idx_nodes_session_status_exists(self, db_path):
        """P2-6: idx_nodes_session_status 인덱스가 DB에 존재해야 함."""
        with contextlib.closing(_conn(db_path)) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name='idx_nodes_session_status'",
            ).fetchone()
        assert row is not None, (
            "idx_nodes_session_status 인덱스가 init_db()에 의해 생성되지 않음"
        )


# ---------------------------------------------------------------------------
# P3-1: restore_cmd format — space after action='restore',
# ---------------------------------------------------------------------------

class TestP33HowToRestoreFormat:

    def test_how_to_restore_has_space_after_action(self, db_path):
        """P3-3: how_to_restore 템플릿도 restore_cmd와 동일한 공백 포맷이어야 함.

        현재 how_to_restore: "action='restore',session_id=..." (공백 없음)
        restore_cmd:          "action='restore', session_id=..." (공백 있음)
        → 불일치 (RED).
        """
        think(db_path, "s1", "node_a", "Objective")
        s = status(db_path, "s1")
        how = s["restoration_manifest"]["how_to_restore"]
        assert "action='restore', session_id=" in how, (
            f"how_to_restore에 공백 누락 또는 포맷 불일치: {how!r}"
        )


class TestP31RestoreCmdFormat:

    def test_status_restore_cmd_has_space_after_action(self, db_path):
        """P3-1: status restore_cmd 형식 — action='restore', session_id= (공백 포함)."""
        think(db_path, "s1", "node_a", "Objective")
        s = status(db_path, "s1")
        cmd = s["restoration_manifest"]["nodes"][0]["restore_cmd"]
        assert "action='restore', session_id=" in cmd, (
            f"restore_cmd에 공백 없음: {cmd!r}"
        )

    def test_restore_list_cmd_has_space_after_action(self, db_path):
        """P3-1: restore(ccr_hash=None) 목록의 restore_cmd도 공백 포함."""
        think(db_path, "s1", "node_a", "Objective")
        result = restore(db_path, "s1")
        cmd = result["restorable_nodes"][0]["restore_cmd"]
        assert "action='restore', session_id=" in cmd, (
            f"restorable_nodes restore_cmd에 공백 없음: {cmd!r}"
        )
