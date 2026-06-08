"""
RED-phase tests for:
  P3-9 : context_pressure must exclude INVALIDATED nodes from COUNT
  P3-12: blank/whitespace node_name and session_id must raise ValueError

These tests FAIL before the GREEN implementation.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.server import call_dag_thinking, init_db, _PRESSURE_MEDIUM


PAYLOAD = (
    "The key finding from this analysis is that the current architecture has a critical bottleneck "
    "in the data pipeline. The assumption is that horizontal scaling will resolve the throughput issue. "
    "Evidence from load tests shows that latency doubles beyond 500 concurrent connections. "
    "Therefore, the conclusion is to implement a message queue to decouple producers from consumers. "
    "This result must be addressed before the next production release to avoid system failure."
)


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test_bugfixes.db")
    init_db(path)
    return path


def think(db, sid, name, ttype, payload=None, depends_on=None):
    return call_dag_thinking(
        db_path=db, action="think", session_id=sid,
        node_name=name, thought_type=ttype,
        payload=payload if payload is not None else PAYLOAD,
        depends_on=depends_on or [],
    )


def invalidate(db, sid, target, reason="test"):
    return call_dag_thinking(
        db_path=db, action="invalidate", session_id=sid,
        target_node=target, reason=reason,
    )


# ---------------------------------------------------------------------------
# P3-9: context_pressure must NOT count INVALIDATED nodes
# ---------------------------------------------------------------------------

class TestContextPressureExcludesInvalidated:

    def test_invalidated_chain_not_counted(self, db_path):
        """P3-9: 체인 전체 INVALIDATED 후 새 노드 1개 → level == 'low'.

        현재 코드는 INVALIDATED 포함 COUNT → 'medium' 반환 (RED).
        """
        # Build chain: n0 → n1 → … → n{PRESSURE_MEDIUM-1}
        think(db_path, "s1", "n0", "Objective")
        prev = "n0"
        for i in range(1, _PRESSURE_MEDIUM):
            think(db_path, "s1", f"n{i}", "Hypothesis", depends_on=[prev])
            prev = f"n{i}"
        # Invalidate root → cascades to ALL nodes in chain
        invalidate(db_path, "s1", "n0")
        # Add one fresh COMPLETED node
        result = think(db_path, "s1", "fresh", "Objective")
        level = result["context_pressure"]["level"]
        assert level == "low", (
            f"INVALIDATED 노드가 COUNT에 포함됨: level='{level}' (expected 'low'). "
            f"node_count={result['context_pressure']['node_count']}"
        )

    def test_node_count_reflects_completed_only(self, db_path):
        """P3-9: context_pressure.node_count == COMPLETED 노드 수 (INVALIDATED 제외).

        현재 코드는 전체 노드를 COUNT → node_count가 3이 됨 (RED).
        """
        think(db_path, "s1", "n0", "Objective")
        think(db_path, "s1", "n1", "Hypothesis", depends_on=["n0"])
        # Invalidate n0 → n0, n1 both INVALIDATED
        invalidate(db_path, "s1", "n0")
        # One COMPLETED node
        result = think(db_path, "s1", "new_node", "Objective")
        node_count = result["context_pressure"]["node_count"]
        assert node_count == 1, (
            f"node_count가 INVALIDATED를 포함: {node_count} (expected 1)"
        )


# ---------------------------------------------------------------------------
# P3-12: Blank/whitespace input validation
# ---------------------------------------------------------------------------

class TestBlankInputValidation:

    def test_blank_node_name_raises(self, db_path):
        """P3-12: 공백 node_name → ValueError.

        현재 `if not node_name:` 는 '   '를 통과시킴 (RED).
        """
        with pytest.raises((ValueError, Exception)):
            think(db_path, "s1", "   ", "Objective")

    def test_blank_session_id_raises(self, db_path):
        """P3-12: 공백 session_id → ValueError.

        현재 session_id 검증 없음 (RED).
        """
        with pytest.raises((ValueError, Exception)):
            think(db_path, "   ", "some_node", "Objective")

    def test_tab_newline_node_name_raises(self, db_path):
        """P3-12: tab/newline 포함 node_name도 거부."""
        with pytest.raises((ValueError, Exception)):
            think(db_path, "s1", "\t\n", "Objective")

    def test_tab_newline_session_id_raises(self, db_path):
        """P3-12: tab/newline 포함 session_id도 거부."""
        with pytest.raises((ValueError, Exception)):
            think(db_path, "\t  \n", "some_node", "Objective")
