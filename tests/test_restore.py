"""action='restore' 행위 테스트 — 목록, 원본 왕복, 세션 격리, 경고.

PLAN.md §3 restore 명세 + §8 체크리스트 C16~C18, SEC-1 커버.
"""

import pytest

from tests.helpers import PAYLOAD, invalidate, restore, think


class TestRestoreList:
    def test_no_hash_lists_restorable_nodes(self, db_path):
        """C16: ccr_hash 없이 호출 → 세션 내 전체 목록."""
        r1 = think(db_path, "s1", "a", "Objective")
        r2 = think(db_path, "s1", "b", "Hypothesis")
        nodes = restore(db_path, "s1")["restorable_nodes"]
        assert [n["name"] for n in nodes] == ["a", "b"]
        assert {n["ccr_hash"] for n in nodes} == {r1["ccr_hash"], r2["ccr_hash"]}
        # CLEAN-14: restore_cmd 포맷이 status 매니페스트와 byte-level 동일 (단일 소스)
        expected = (
            f"dag_thinking(action='restore', session_id={'s1'!r}, ccr_hash={r1['ccr_hash']!r})"
        )
        assert nodes[0]["restore_cmd"] == expected
        for n in nodes:
            assert n["status"] == "COMPLETED"
            assert n["restore_cmd"].startswith("dag_thinking(action='restore', ")

    def test_empty_session_lists_nothing(self, db_path):
        assert restore(db_path, "empty")["restorable_nodes"] == []


class TestRestoreRoundtrip:
    def test_original_payload_byte_identical(self, db_path):
        """C17: 압축된 노드의 restore → 원본과 byte-level 동일."""
        r = think(db_path, "s1", "a", "Objective")  # PAYLOAD는 압축 대상 길이
        out = restore(db_path, "s1", r["ccr_hash"])
        assert out["original_payload"] == PAYLOAD
        assert out["node_name"] == "a"
        assert out["tokens"] > 0

    def test_unknown_hash_rejected(self, db_path):
        """미존재 hash → ValueError."""
        with pytest.raises(ValueError, match="not found"):
            restore(db_path, "s1", "0" * 24)

    def test_cross_session_scoping(self, db_path):
        """C18/SEC-1: 타 세션 hash 복원 거부 + 원소유 세션 ID 비노출."""
        r = think(db_path, "owner_session", "a", "Objective")
        with pytest.raises(ValueError) as exc_info:
            restore(db_path, "other_session", r["ccr_hash"])
        msg = str(exc_info.value)
        assert "owner_session" not in msg, f"타 세션 ID 노출: {msg}"
        assert "other_session" in msg


class TestRestoreWarnings:
    def test_invalidated_node_warns(self, db_path):
        """I52(부분)/v0.18: INVALIDATED 노드 복원 시 stale 경고."""
        r = think(db_path, "s1", "a", "Objective")
        invalidate(db_path, "s1", "a")
        out = restore(db_path, "s1", r["ccr_hash"])
        assert out["original_payload"] == PAYLOAD
        assert "INVALIDATED" in out["warning"]
