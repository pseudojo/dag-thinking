"""
RED-phase tests for I11 and I12.

  I11: _action_restore(ccr_hash=None) 목록에 status 필드 추가
  I12: _compute_dag_health INVALIDATED 노드를 구조 분석에서 제외
"""

import pytest

from tests.helpers import think, invalidate, restore, status

_LONG_PAYLOAD = (
    "The key finding from this analysis is that the current architecture has a critical bottleneck "
    "in the data pipeline. The assumption is that horizontal scaling will resolve the throughput issue. "
    "Evidence from load tests shows that latency doubles beyond 500 concurrent connections. "
    "Therefore, the conclusion is to implement a message queue to decouple producers from consumers. "
    "This result must be addressed before the next production release to avoid system failure."
)


# ---------------------------------------------------------------------------
# I11: _action_restore list — status 필드
# ---------------------------------------------------------------------------

class TestRestoreListStatus:

    # T1: COMPLETED 노드 목록 → status == "COMPLETED"
    def test_completed_node_has_status_completed_in_list(self, db_path):
        """I11-T1: COMPLETED 노드 복원 목록에 status='COMPLETED' 포함.

        현재: {name, ccr_hash, restore_cmd} 만 반환 — RED.
        """
        think(db_path, "s1", "node_a", "Objective", payload=_LONG_PAYLOAD)
        result = restore(db_path, "s1")
        entries = result["restorable_nodes"]
        assert len(entries) == 1
        entry = entries[0]
        assert "status" in entry, (
            f"restorable_nodes 항목에 'status' 키 없음 — RED: {list(entry.keys())}"
        )
        assert entry["status"] == "COMPLETED", (
            f"COMPLETED 노드의 status가 'COMPLETED'가 아님: {entry['status']}"
        )

    # T2: INVALIDATED 노드 목록 → status == "INVALIDATED"
    def test_invalidated_node_has_status_invalidated_in_list(self, db_path):
        """I11-T2: INVALIDATED 노드 복원 목록에 status='INVALIDATED' 포함.

        현재: status 필드 없음 → RED.
        """
        think(db_path, "s1", "node_a", "Objective", payload=_LONG_PAYLOAD)
        invalidate(db_path, "s1", "node_a")
        result = restore(db_path, "s1")
        entries = result["restorable_nodes"]
        assert len(entries) == 1
        entry = entries[0]
        assert "status" in entry, "status 키 없음 — RED"
        assert entry["status"] == "INVALIDATED", (
            f"INVALIDATED 노드의 status가 'INVALIDATED'가 아님: {entry['status']}"
        )

    # T3: 혼합 — 각 항목에 올바른 status
    def test_mixed_nodes_have_correct_status_in_list(self, db_path):
        """I11-T3: COMPLETED + INVALIDATED 혼합 → 각 항목 status 정확.

        현재: status 필드 없음 → RED.
        """
        think(db_path, "s1", "node_a", "Objective", payload=_LONG_PAYLOAD)
        think(db_path, "s1", "node_b", "Hypothesis", payload=_LONG_PAYLOAD)
        invalidate(db_path, "s1", "node_a")

        result = restore(db_path, "s1")
        entries = {e["name"]: e for e in result["restorable_nodes"]}

        assert entries["node_a"]["status"] == "INVALIDATED", (
            f"node_a(INVALIDATED)의 status: {entries['node_a'].get('status')}"
        )
        assert entries["node_b"]["status"] == "COMPLETED", (
            f"node_b(COMPLETED)의 status: {entries['node_b'].get('status')}"
        )

    # T4: status 키가 항상 존재 (어떤 노드든)
    def test_status_key_always_present(self, db_path):
        """I11-T4: 모든 restorable_nodes 항목에 status 키 존재."""
        think(db_path, "s1", "n1", "Objective", payload=_LONG_PAYLOAD)
        think(db_path, "s1", "n2", "Hypothesis", payload=_LONG_PAYLOAD)
        think(db_path, "s1", "n3", "Evidence", payload=_LONG_PAYLOAD)
        invalidate(db_path, "s1", "n2")

        result = restore(db_path, "s1")
        for entry in result["restorable_nodes"]:
            assert "status" in entry, (
                f"항목 '{entry['name']}'에 status 없음"
            )

    # T5: 빈 세션 → restorable_nodes == [] (회귀)
    def test_empty_session_list_unaffected(self, db_path):
        """I11-T5: 노드 없는 세션 → 빈 목록, 회귀 없음."""
        result = restore(db_path, "empty_session")
        assert result["restorable_nodes"] == []


# ---------------------------------------------------------------------------
# I12: _compute_dag_health — INVALIDATED 노드 제외
# ---------------------------------------------------------------------------

class TestDagHealthExcludesInvalidated:

    # T6: INVALIDATED 노드가 orphan_nodes에 미포함
    def test_invalidated_node_not_in_orphan_nodes(self, db_path):
        """I12-T6: 1 COMPLETED + 1 INVALIDATED, 엣지 없음 → orphan_nodes == [].

        현재: node_names에 INVALIDATED 포함 → INVALIDATED가 orphan으로 잡힘 — RED.
        """
        think(db_path, "s1", "active_node", "Objective", payload=_LONG_PAYLOAD)
        think(db_path, "s1", "dead_node", "Hypothesis", payload=_LONG_PAYLOAD)
        invalidate(db_path, "s1", "dead_node")

        result = status(db_path, "s1")
        orphans = result["dag_health"]["orphan_nodes"]
        assert "dead_node" not in orphans, (
            f"INVALIDATED 노드 'dead_node'가 orphan으로 감지됨 — RED: {orphans}"
        )

    # T7: COMPLETED 1개이면 orphan 없음 (INVALIDATED 때문에 잘못된 2개 판정 방지)
    def test_single_completed_no_orphan_despite_invalidated(self, db_path):
        """I12-T7: len(COMPLETED)==1 이면 orphan 체크 스킵 → orphan_nodes == [].

        현재: len(node_names)==2 이므로 orphan 체크 진입 → 잘못된 orphan 반환 — RED.
        """
        think(db_path, "s1", "only_live", "Objective", payload=_LONG_PAYLOAD)
        think(db_path, "s1", "gone", "Hypothesis", payload=_LONG_PAYLOAD)
        invalidate(db_path, "s1", "gone")

        result = status(db_path, "s1")
        orphans = result["dag_health"]["orphan_nodes"]
        assert orphans == [], (
            f"COMPLETED 1개 세션의 orphan_nodes가 비어있지 않음 — RED: {orphans}"
        )

    # T8: INVALIDATED root가 max_depth에 기여 방지
    def test_invalidated_root_excluded_from_max_depth(self, db_path):
        """I12-T8: INVALIDATED 독립 노드가 BFS root로 잡혀 max_depth를 왜곡하지 않음.

        A(INVALIDATED), B→C (COMPLETED chain) → max_depth == 1 (B→C 기준)
        현재: A가 root로 BFS 진입 → 잘못된 계산 가능 — RED.
        """
        # B→C COMPLETED chain (max_depth=1)
        think(db_path, "s1", "b_node", "Objective", payload=_LONG_PAYLOAD)
        think(db_path, "s1", "c_node", "Hypothesis", payload=_LONG_PAYLOAD,
              depends_on=["b_node"])
        # A는 독립 INVALIDATED
        think(db_path, "s1", "a_node", "Evidence", payload=_LONG_PAYLOAD)
        invalidate(db_path, "s1", "a_node")

        result = status(db_path, "s1")
        max_depth = result["dag_health"]["max_depth"]
        assert max_depth == 1, (
            f"B→C 체인(max_depth=1)인데 INVALIDATED 포함 계산으로 오류: {max_depth}"
        )

    # T9: total_nodes가 COMPLETED 기준 (health_hint 임계값 기준)
    def test_total_nodes_based_on_completed_only(self, db_path):
        """I12-T9: COMPLETED=3, INVALIDATED=3 (총6개, 모두 연결) → Synthesis 경고 미노출.

        orphan이 없어야 Synthesis 경고 경로에 진입.
        COMPLETED=3 < 5 이므로 경고 없어야 함.
        현재: total_nodes=6 >= 5 → 잘못된 "nodes without Synthesis" 경고 발생 — RED.
        """
        # A→B→C 체인 생성 후 A 무효화 → cascade → A,B,C 모두 INVALIDATED (엣지 유지)
        think(db_path, "s1", "a", "Objective", payload=_LONG_PAYLOAD)
        think(db_path, "s1", "b", "Hypothesis", payload=_LONG_PAYLOAD, depends_on=["a"])
        think(db_path, "s1", "c", "Evidence", payload=_LONG_PAYLOAD, depends_on=["b"])
        invalidate(db_path, "s1", "a")  # cascade → a, b, c 모두 INVALIDATED

        # D→E→F COMPLETED 체인 (3개, Synthesis 없음)
        think(db_path, "s1", "d", "Objective", payload=_LONG_PAYLOAD)
        think(db_path, "s1", "e", "Hypothesis", payload=_LONG_PAYLOAD, depends_on=["d"])
        think(db_path, "s1", "f", "Evidence", payload=_LONG_PAYLOAD, depends_on=["e"])

        result = status(db_path, "s1")
        hint = result["dag_health"]["health_hint"]
        assert "nodes without Synthesis" not in hint, (
            f"COMPLETED=3인데 'nodes without Synthesis' 경고 노출됨 — RED: {hint!r}"
        )

    # T10: 순수 COMPLETED 체인 max_depth 회귀
    def test_pure_completed_chain_max_depth_regression(self, db_path):
        """I12-T10: A→B→C 모두 COMPLETED → max_depth == 2 (회귀 없음)."""
        think(db_path, "s1", "a", "Objective", payload=_LONG_PAYLOAD)
        think(db_path, "s1", "b", "Hypothesis", payload=_LONG_PAYLOAD, depends_on=["a"])
        think(db_path, "s1", "c", "Evidence", payload=_LONG_PAYLOAD, depends_on=["b"])

        result = status(db_path, "s1")
        assert result["dag_health"]["max_depth"] == 2

    # T11: 모든 노드 INVALIDATED → 안전한 빈 결과
    def test_all_nodes_invalidated_safe_result(self, db_path):
        """I12-T11: 모든 노드 INVALIDATED → orphan_nodes==[], max_depth==0."""
        think(db_path, "s1", "n1", "Objective", payload=_LONG_PAYLOAD)
        think(db_path, "s1", "n2", "Hypothesis", payload=_LONG_PAYLOAD)
        invalidate(db_path, "s1", "n1")
        invalidate(db_path, "s1", "n2")

        result = status(db_path, "s1")
        health = result["dag_health"]
        assert health["orphan_nodes"] == [], (
            f"전체 INVALIDATED 세션에서 orphan_nodes 비어있지 않음: {health['orphan_nodes']}"
        )
        assert health["max_depth"] == 0, (
            f"전체 INVALIDATED 세션에서 max_depth != 0: {health['max_depth']}"
        )
