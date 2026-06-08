"""
RED-phase tests for:
  BUG-1: tokens_saved double-counts on node update
  P3-9 : context_pressure must exclude INVALIDATED nodes from COUNT
  P3-12: blank/whitespace node_name and session_id must raise ValueError
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.server import _PRESSURE_MEDIUM
from tests.helpers import think, invalidate, status


# ---------------------------------------------------------------------------
# BUG-1: tokens_saved must NOT double-count on node update
# ---------------------------------------------------------------------------

_PAYLOAD_A = (
    "Initial analysis shows critical bottleneck in database layer. "
    "The key finding is that N+1 queries cause exponential load. "
    "Therefore we must implement eager loading as the primary solution. "
    "The assumption is that ORM fixes suffice without raw SQL rewrites. "
    "Conclusion: phased rollout minimizes risk to production stability."
)
_PAYLOAD_B = (
    "Revised analysis reveals message broker is the actual bottleneck. "
    "The key finding is that vertical scaling is more cost-effective here. "
    "Therefore we must implement connection pooling as the primary solution. "
    "The assumption is that pooling reduces latency by 70 percent at peak. "
    "Conclusion: validate in staging environment before production deployment."
)


class TestTokensSavedOnUpdate:

    def test_update_same_node_no_double_count(self, db_path):
        """BUG-1: 같은 노드를 다른 payload로 재생성해도 session total이 이중 집계되지 않음.

        현재 코드는 update 경로에서도 tokens_saved를 무조건 더하므로 이중 집계 발생 (RED).
        """
        r1 = think(db_path, "s1", "n1", "Objective", payload=_PAYLOAD_A)
        r2 = think(db_path, "s1", "n1", "Objective", payload=_PAYLOAD_B)
        s = status(db_path, "s1")
        expected = r2["compression"]["tokens_saved"]
        actual = s["metrics"]["tokens_saved"]
        assert actual == expected, (
            f"노드 업데이트 후 tokens_saved 이중 집계: actual={actual}, expected={expected}. "
            f"r1.saved={r1['compression']['tokens_saved']}, r2.saved={r2['compression']['tokens_saved']}"
        )

    def test_update_same_payload_no_double_count(self, db_path):
        """BUG-1 변형: 동일 payload로 재생성해도 이중 집계 없음."""
        r1 = think(db_path, "s1", "n1", "Objective", payload=_PAYLOAD_A)
        r2 = think(db_path, "s1", "n1", "Objective", payload=_PAYLOAD_A)
        s = status(db_path, "s1")
        expected = r2["compression"]["tokens_saved"]
        assert s["metrics"]["tokens_saved"] == expected, (
            f"동일 payload 재생성 후 이중 집계: total={s['metrics']['tokens_saved']}, expected={expected}"
        )

    def test_multi_node_update_accumulates_correctly(self, db_path):
        """BUG-1: 두 노드 중 하나를 업데이트해도 session total이 올바름."""
        r1 = think(db_path, "s1", "n1", "Objective", payload=_PAYLOAD_A)
        r2 = think(db_path, "s1", "n2", "Hypothesis", payload=_PAYLOAD_A)
        # n1을 새 payload로 업데이트
        r1b = think(db_path, "s1", "n1", "Objective", payload=_PAYLOAD_B)
        s = status(db_path, "s1")
        expected = r1b["compression"]["tokens_saved"] + r2["compression"]["tokens_saved"]
        assert s["metrics"]["tokens_saved"] == expected, (
            f"멀티 노드 업데이트 후 집계 오류: actual={s['metrics']['tokens_saved']}, expected={expected}"
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
