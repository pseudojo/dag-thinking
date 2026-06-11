"""action='invalidate' 행위 테스트 — 캐스케이드 무효화, 존재 검증, 재생성 복귀.

PLAN.md §3 invalidate 명세 + §8 체크리스트 C19~C21, C24 커버.
"""

import pytest

from tests.helpers import invalidate, status, think


def _node_status(db_path, sid, name):
    nodes = status(db_path, sid)["dag"]["nodes"]
    return next(n["status"] for n in nodes if n["name"] == name)


class TestInvalidate:
    def test_single_node_invalidated(self, db_path):
        """C19: 단일 노드 무효화 — 응답 목록 + reason 에코 + 상태 전이."""
        think(db_path, "s1", "a", "Objective")
        r = invalidate(db_path, "s1", "a", reason="premise broken")
        assert r["invalidated"] == ["a"]
        assert r["reason"] == "premise broken"
        assert r["hint"]
        assert _node_status(db_path, "s1", "a") == "INVALIDATED"

    def test_cascade_to_descendants(self, db_path):
        """C20: A→B→C에서 A 무효화 → 전부 INVALIDATED."""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        think(db_path, "s1", "c", "Evidence", depends_on=["b"])
        r = invalidate(db_path, "s1", "a")
        assert sorted(r["invalidated"]) == ["a", "b", "c"]

    def test_sibling_branch_unaffected(self, db_path):
        """형제 분기는 보존 — A→B, A→C에서 B 무효화 → C는 COMPLETED."""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        think(db_path, "s1", "c", "Hypothesis", depends_on=["a"])
        invalidate(db_path, "s1", "b")
        assert _node_status(db_path, "s1", "c") == "COMPLETED"
        assert _node_status(db_path, "s1", "a") == "COMPLETED"

    def test_nonexistent_node_rejected(self, db_path):
        """C24/I03: 미존재 노드 → ValueError, 노드명 + 안내 포함."""
        with pytest.raises(ValueError, match="ghost"):
            invalidate(db_path, "s1", "ghost")

    def test_blank_target_rejected(self, db_path):
        """I41/I47: 공백 전용 target_node → ValueError."""
        for bad in (None, "", "   "):
            with pytest.raises(ValueError, match="target_node"):
                invalidate(db_path, "s1", bad)

    def test_reinvalidation_reports_empty(self, db_path):
        """멱등 경계: 이미 INVALIDATED인 노드 재무효화 → 신규 목록 빈 리스트."""
        think(db_path, "s1", "a", "Objective")
        invalidate(db_path, "s1", "a")
        assert invalidate(db_path, "s1", "a")["invalidated"] == []

    def test_recreate_restores_completed(self, db_path):
        """C21: 무효화된 노드를 동일 이름으로 재생성 → COMPLETED 복귀."""
        think(db_path, "s1", "a", "Objective")
        invalidate(db_path, "s1", "a")
        r = think(db_path, "s1", "a", "Objective")
        assert r["status"] == "updated"
        assert _node_status(db_path, "s1", "a") == "COMPLETED"
