"""
dag-thinking v0.14 improvements — TDD RED phase
I35: _action_think PERF-2 완성 (읽기 쿼리 트랜잭션 외부 이동)
I36: note 필드 길이 상한 (_MAX_NOTE_LEN=500)
I37: _compress_list 최소 k=2 (다중 아이템 과잉 압축 방지)
"""

import pytest

from src.compressor import _compress_list, _RATIO_LONG, _RATIO_SHORT, _RATIO_TINY
from src.server import call_dag_thinking, init_db
from tests.helpers import think, status, PAYLOAD


# ---------------------------------------------------------------------------
# I35: _action_think PERF-2 완성 — 동작 동등성 보장
# ---------------------------------------------------------------------------

class TestActionThinkPerf2Reads:
    """I35: reads moved outside write transaction — behavior unchanged"""

    def test_basic_think_still_works(self, db_path):
        """T35-1: 단일 노드 think() 정상 처리"""
        result = think(db_path, "s1", "n", "Objective", PAYLOAD)
        assert result["status"] in ("created", "updated")

    def test_parent_context_resolved_for_existing_parent(self, db_path):
        """T35-2: 기존 부모 노드 → parent_context 포함"""
        think(db_path, "s1", "parent", "Objective", PAYLOAD)
        result = think(db_path, "s1", "child", "Hypothesis", PAYLOAD,
                       depends_on=["parent"])
        assert "parent_context" in result
        assert "parent" in result["parent_context"]
        assert "error" not in result["parent_context"]["parent"]

    def test_missing_parent_returns_error_entry(self, db_path):
        """T35-3: 존재하지 않는 부모 → parent_context error 포함"""
        result = think(db_path, "s1", "child", "Hypothesis", PAYLOAD,
                       depends_on=["nonexist"])
        assert "parent_context" in result
        assert "error" in result["parent_context"]["nonexist"]

    def test_self_reference_cycle_raises(self, db_path):
        """T35-4: 자기 참조 사이클 → ValueError"""
        think(db_path, "s1", "n", "Objective", PAYLOAD)
        with pytest.raises(ValueError, match="[Cc]ycle"):
            think(db_path, "s1", "n", "Objective", PAYLOAD, depends_on=["n"])

    def test_indirect_cycle_raises(self, db_path):
        """T35-5: A→B→A 간접 사이클 → ValueError"""
        think(db_path, "s1", "a", "Objective", PAYLOAD)
        think(db_path, "s1", "b", "Hypothesis", PAYLOAD, depends_on=["a"])
        with pytest.raises(ValueError, match="[Cc]ycle"):
            think(db_path, "s1", "a", "Evidence", PAYLOAD, depends_on=["b"])

    def test_cycle_error_does_not_leave_session_dirty(self, db_path):
        """T35-6: 사이클 ValueError 발생 시 노드 미생성 (트랜잭션 롤백 보장)"""
        think(db_path, "s1", "a", "Objective", PAYLOAD)
        think(db_path, "s1", "b", "Hypothesis", PAYLOAD, depends_on=["a"])
        with pytest.raises(ValueError):
            think(db_path, "s1", "a", "Evidence", PAYLOAD, depends_on=["b"])
        # "a" should still exist as Objective, not re-created as Evidence mid-cycle
        s = status(db_path, "s1")
        node_types = {n["name"]: n["thought_type"] for n in s["dag"]["nodes"]}
        assert node_types.get("a") == "Objective"


# ---------------------------------------------------------------------------
# I36: note 필드 길이 상한 (_MAX_NOTE_LEN=500)
# ---------------------------------------------------------------------------

class TestNoteLengthValidation:
    """I36: note exceeds 500 chars → ValueError"""

    def test_empty_note_passes(self, db_path):
        """T36-1: note='' → 정상 처리"""
        result = think(db_path, "s1", "n", "Objective", PAYLOAD, note="")
        assert result["status"] in ("created", "updated")

    def test_note_exactly_500_passes(self, db_path):
        """T36-2: note 500자 → 정상 처리 (상한 경계값 통과)"""
        result = think(db_path, "s1", "n", "Objective", PAYLOAD, note="x" * 500)
        assert result["status"] in ("created", "updated")

    def test_note_exactly_501_raises(self, db_path):
        """T36-3: note 501자 → ValueError (상한 경계값 위반)"""
        with pytest.raises(ValueError, match="note"):
            think(db_path, "s1", "n", "Objective", PAYLOAD, note="x" * 501)

    def test_note_1000_raises(self, db_path):
        """T36-4: note 1000자 → ValueError"""
        with pytest.raises(ValueError, match="note"):
            think(db_path, "s1", "n", "Objective", PAYLOAD, note="x" * 1000)


# ---------------------------------------------------------------------------
# I37: _compress_list 최소 k=2 (다중 아이템 과잉 압축 방지)
# ---------------------------------------------------------------------------

def _make_list_text(n: int, chars_per_item: int = 80) -> str:
    """n개의 bullet 아이템으로 구성된 목록 텍스트 생성."""
    return "\n".join(f"- Item {i+1}: {'x' * (chars_per_item - 12)}" for i in range(n))


class TestCompressListMinK:
    """I37: _compress_list — 다중 아이템 목록 최소 2개 보존"""

    def test_single_item_list_keeps_1(self):
        """T37-1: 1-item 목록 → k=1 (변경 없음)"""
        text = _make_list_text(1, 100)
        result = _compress_list(text, _RATIO_LONG)
        lines = [l for l in result.splitlines() if l.strip()]
        assert len(lines) == 1

    def test_two_item_list_ratio_42_keeps_2(self):
        """T37-2: 2-item 목록, ratio=0.42 → k=max(2,round(0.84))=max(2,1)=2"""
        text = _make_list_text(2, 100)
        result = _compress_list(text, _RATIO_LONG)
        lines = [l for l in result.splitlines() if l.strip()]
        assert len(lines) == 2

    def test_three_item_list_ratio_42_keeps_at_least_2(self):
        """T37-3: 3-item 목록, ratio=0.42 → k=max(2,1)=2 (버그 픽스 핵심)"""
        text = _make_list_text(3, 100)
        result = _compress_list(text, _RATIO_LONG)
        lines = [l for l in result.splitlines() if l.strip()]
        assert len(lines) >= 2, (
            f"3-item 목록을 {len(lines)}개로 과잉 압축함 (최소 2개 보존 필요)"
        )

    def test_three_item_list_ratio_58_keeps_2(self):
        """T37-4: 3-item 목록, ratio=0.58 → k=max(2,round(1.74))=max(2,2)=2"""
        text = _make_list_text(3, 100)
        result = _compress_list(text, _RATIO_SHORT)
        lines = [l for l in result.splitlines() if l.strip()]
        assert len(lines) == 2

    def test_ten_item_list_ratio_42_keeps_4(self):
        """T37-5: 10-item 목록, ratio=0.42 → k=max(2,4)=4 (기존 동일)"""
        text = _make_list_text(10, 80)
        result = _compress_list(text, _RATIO_LONG)
        lines = [l for l in result.splitlines() if l.strip()]
        assert len(lines) == 4
