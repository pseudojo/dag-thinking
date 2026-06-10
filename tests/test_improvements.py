"""
dag-thinking improvement tests (I01–I05)
TDD RED phase — written before implementation.

IMPROVEMENTS.md 명세 기준:
  I01: _has_cycle 단순화
  I02: think 응답에 session_total_saved 추가
  I03: invalidate target_node 존재 검증
  I04: status 노드에 created_at 포함
  I05: next_hint 컨텍스트 기반 개선
"""

import pytest

from tests.helpers import invalidate, status, think

# ---------------------------------------------------------------------------
# I01: _has_cycle — 3-hop 전이 사이클 및 다이아몬드 구조
# ---------------------------------------------------------------------------


class TestHasCycleSimplified:
    """IC01-IC04: _has_cycle 정확성 검증"""

    def test_ic01_regression_a_b_a_cycle(self, db_path):
        """IC01: 기존 A→B→A 사이클 감지 회귀 없음"""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        with pytest.raises((ValueError, Exception)):
            think(db_path, "s1", "a", "Critique", depends_on=["b"])

    def test_ic02_self_reference_cycle(self, db_path):
        """IC02: 자기 참조 사이클 A depends_on A"""
        think(db_path, "s1", "a", "Objective")
        with pytest.raises((ValueError, Exception)) as exc_info:
            think(db_path, "s1", "a", "Critique", depends_on=["a"])
        assert "cycle" in str(exc_info.value).lower() or "self" in str(exc_info.value).lower()

    def test_ic03_three_hop_transitive_cycle(self, db_path):
        """IC03: A→B→C 후 C depends_on A 시도 → 사이클"""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        think(db_path, "s1", "c", "Evidence", depends_on=["b"])
        with pytest.raises((ValueError, Exception)):
            think(db_path, "s1", "a", "Synthesis", depends_on=["c"])

    def test_ic04_diamond_structure_allowed(self, db_path):
        """IC04: A→B, A→C, B→D, C→D 다이아몬드 구조 — 사이클 아님"""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        think(db_path, "s1", "c", "Assumption", depends_on=["a"])
        think(db_path, "s1", "d", "Synthesis", depends_on=["b", "c"])
        s = status(db_path, "s1")
        names = [n["name"] for n in s["dag"]["nodes"]]
        assert "d" in names  # 생성 성공


# ---------------------------------------------------------------------------
# I02: session_total_saved
# ---------------------------------------------------------------------------

class TestSessionTotalSaved:
    """IC05-IC07: think 응답에 session_total_saved 포함"""

    def test_ic05_first_think_has_session_total_saved(self, db_path):
        """IC05: think 후 compression.session_total_saved 필드 존재"""
        result = think(db_path, "s1", "n1", "Objective")
        assert "compression" in result
        assert "session_total_saved" in result["compression"], (
            "compression 응답에 session_total_saved 누락 (PLAN.md 명세 위반)"
        )

    def test_ic06_session_total_saved_accumulates(self, db_path):
        """IC06: 두 번째 think 후 session_total_saved >= 첫 번째"""
        r1 = think(db_path, "s1", "n1", "Objective")
        r2 = think(db_path, "s1", "n2", "Hypothesis")
        total1 = r1["compression"]["session_total_saved"]
        total2 = r2["compression"]["session_total_saved"]
        assert total2 >= total1, (
            f"session_total_saved가 감소함: {total1} → {total2}"
        )

    def test_ic07_passthrough_node_has_session_total_saved(self, db_path):
        """IC07: 압축 안 된 노드(tokens_saved=0)도 session_total_saved 포함"""
        # 먼저 긴 노드로 누적값 만들기
        think(db_path, "s1", "n1", "Objective")
        # 짧은 노드 (passthrough)
        short = "This is a short payload for passthrough testing. No compression." * 1
        # 80자 이상이지만 압축 안 되는 경우 확인
        short_payload = "Key finding: system stable. No errors. All metrics nominal. Status: green." + " " * 10
        if len(short_payload) >= 80:
            r = think(db_path, "s1", "n2", "Evidence", payload=short_payload[:200])
            assert "session_total_saved" in r["compression"]


# ---------------------------------------------------------------------------
# I03: invalidate node existence check
# ---------------------------------------------------------------------------

class TestInvalidateNodeNotFound:
    """IC08-IC10: invalidate target_node 존재 검증"""

    def test_ic08_invalidate_nonexistent_node_raises(self, db_path):
        """IC08: 존재하지 않는 노드 invalidate → ValueError"""
        with pytest.raises((ValueError, Exception)):
            invalidate(db_path, "s1", "ghost_node")

    def test_ic09_error_message_contains_node_name(self, db_path):
        """IC09: 에러 메시지에 target_node 이름 포함"""
        with pytest.raises((ValueError, Exception)) as exc_info:
            invalidate(db_path, "s1", "missing_node_xyz")
        assert "missing_node_xyz" in str(exc_info.value)

    def test_ic10_existing_node_invalidate_still_works(self, db_path):
        """IC10: 존재하는 노드 invalidate 회귀 없음"""
        think(db_path, "s1", "real_node", "Objective")
        result = invalidate(db_path, "s1", "real_node")
        assert "real_node" in result["invalidated"]


# ---------------------------------------------------------------------------
# I04: created_at in status nodes
# ---------------------------------------------------------------------------

class TestStatusCreatedAt:
    """IC11-IC12: status 응답 노드에 created_at 포함"""

    def test_ic11_nodes_have_created_at(self, db_path):
        """IC11: status().dag.nodes[*]에 created_at 필드 존재"""
        think(db_path, "s1", "n1", "Objective")
        s = status(db_path, "s1")
        assert len(s["dag"]["nodes"]) > 0
        node = s["dag"]["nodes"][0]
        assert "created_at" in node, (
            "status dag.nodes에 created_at 필드 누락"
        )

    def test_ic12_created_at_is_non_null_string(self, db_path):
        """IC12: created_at이 None이 아닌 문자열"""
        think(db_path, "s1", "n1", "Objective")
        s = status(db_path, "s1")
        node = s["dag"]["nodes"][0]
        assert node["created_at"] is not None
        assert isinstance(node["created_at"], str)
        assert len(node["created_at"]) > 0


# ---------------------------------------------------------------------------
# I05: next_hint contextual
# ---------------------------------------------------------------------------

class TestNextHintContextual:
    """IC13-IC15: thought_type 기반 next_hint"""

    def test_ic13_objective_hints_hypothesis_or_assumption(self, db_path):
        """IC13: Objective 노드 → hint에 'Hypothesis' 또는 'Assumption' 포함"""
        result = think(db_path, "s1", "obj", "Objective")
        hint = result.get("next_hint", "")
        assert "Hypothesis" in hint or "Assumption" in hint, (
            f"Objective 노드의 hint가 다음 단계를 안내하지 않음: '{hint}'"
        )

    def test_ic14_synthesis_hints_action_or_status(self, db_path):
        """IC14: Synthesis 노드 → hint에 'Action' 또는 'status' 포함"""
        result = think(db_path, "s1", "syn", "Synthesis")
        hint = result.get("next_hint", "")
        assert "Action" in hint or "status" in hint, (
            f"Synthesis 노드의 hint가 다음 단계를 안내하지 않음: '{hint}'"
        )

    def test_ic15_action_hints_status(self, db_path):
        """IC15: Action 노드 → hint에 'status()' 포함"""
        result = think(db_path, "s1", "act", "Action")
        hint = result.get("next_hint", "")
        assert "status()" in hint or "status" in hint, (
            f"Action 노드의 hint가 status() 호출을 안내하지 않음: '{hint}'"
        )

    def test_hint_critique_mentions_synthesis(self, db_path):
        """Critique 노드 → hint에 'Synthesis' 포함"""
        result = think(db_path, "s1", "crit", "Critique")
        hint = result.get("next_hint", "")
        assert "Synthesis" in hint, (
            f"Critique 노드의 hint가 Synthesis를 안내하지 않음: '{hint}'"
        )

    def test_hint_evidence_mentions_synthesis(self, db_path):
        """Evidence 노드 → hint에 'Synthesis' 또는 'Critique' 포함"""
        result = think(db_path, "s1", "ev", "Evidence")
        hint = result.get("next_hint", "")
        assert "Synthesis" in hint or "Critique" in hint, (
            f"Evidence 노드의 hint가 다음 단계를 안내하지 않음: '{hint}'"
        )
