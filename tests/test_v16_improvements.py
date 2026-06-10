"""
dag-thinking v0.16 improvements — TDD RED phase

I42: _action_think 응답에 thought_type 필드 추가
I43: _action_status dag.nodes에 ccr_hash 필드 추가
I44: _is_list_content — `+` 불릿 프리픽스 지원 (GFM)
I45: _compute_dag_health — total_nodes 카운트 추가
"""

import pytest

from src.compressor import _is_list_content
from src.server import call_dag_thinking
from tests.helpers import think, status, invalidate, PAYLOAD


# ---------------------------------------------------------------------------
# I42: think 응답에 thought_type 필드
# ---------------------------------------------------------------------------

class TestThinkResponseThoughtType:
    """I42: action='think' 응답에 thought_type 필드가 포함되어야 한다."""

    def test_objective_node_has_thought_type(self, db_path):
        """I42-T1: Objective 노드 생성 → 응답에 thought_type=='Objective'"""
        result = think(db_path, "s1", "n", "Objective", PAYLOAD)
        assert "thought_type" in result, "think 응답에 thought_type 키가 없음"
        assert result["thought_type"] == "Objective"

    def test_hypothesis_node_has_thought_type(self, db_path):
        """I42-T2: Hypothesis 노드 → 응답에 thought_type=='Hypothesis'"""
        result = think(db_path, "s1", "n", "Hypothesis", PAYLOAD)
        assert result["thought_type"] == "Hypothesis"

    def test_action_node_has_thought_type(self, db_path):
        """I42-T3: Action 노드 → 응답에 thought_type=='Action'"""
        result = think(db_path, "s1", "n", "Action", PAYLOAD)
        assert result["thought_type"] == "Action"

    def test_upsert_returns_thought_type(self, db_path):
        """I42-T4: 동일 node_name 재생성(upsert) → thought_type 필드 유지"""
        think(db_path, "s1", "n", "Objective", PAYLOAD)
        result = think(db_path, "s1", "n", "Critique", PAYLOAD)
        assert "thought_type" in result
        assert result["thought_type"] == "Critique"

    def test_all_valid_thought_types_returned(self, db_path):
        """I42-T5: 7개 모든 VALID_THOUGHT_TYPES → 각각 정확히 반환"""
        types = ["Objective", "Hypothesis", "Assumption", "Evidence",
                 "Critique", "Synthesis", "Action"]
        for i, t in enumerate(types):
            result = think(db_path, "s1", f"node_{i}", t, PAYLOAD)
            assert result["thought_type"] == t, (
                f"{t} 노드의 thought_type이 {result.get('thought_type')}로 잘못 반환됨"
            )


# ---------------------------------------------------------------------------
# I43: status dag.nodes에 ccr_hash 필드
# ---------------------------------------------------------------------------

class TestStatusDagNodesCcrHash:
    """I43: status 응답의 dag.nodes 각 항목에 ccr_hash 필드가 포함되어야 한다."""

    def test_single_node_has_ccr_hash_in_dag_nodes(self, db_path):
        """I43-T1: 노드 1개 세션 status → dag.nodes[0]에 ccr_hash 존재, 24자"""
        think(db_path, "s1", "n1", "Objective", PAYLOAD)
        s = status(db_path, "s1")
        nodes = s["dag"]["nodes"]
        assert len(nodes) == 1
        assert "ccr_hash" in nodes[0], "dag.nodes 항목에 ccr_hash 키 없음"
        assert len(nodes[0]["ccr_hash"]) == 24

    def test_multiple_nodes_all_have_ccr_hash(self, db_path):
        """I43-T2: 노드 3개 → 모든 dag.nodes 항목에 ccr_hash 존재"""
        think(db_path, "s1", "n1", "Objective", PAYLOAD)
        think(db_path, "s1", "n2", "Hypothesis", PAYLOAD)
        think(db_path, "s1", "n3", "Evidence", PAYLOAD)
        s = status(db_path, "s1")
        for node in s["dag"]["nodes"]:
            assert "ccr_hash" in node, f"노드 '{node['name']}'에 ccr_hash 없음"

    def test_empty_session_dag_nodes_empty(self, db_path):
        """I43-T3: 빈 세션 status → dag.nodes==[] (오류 없음)"""
        s = status(db_path, "empty_session")
        assert s["dag"]["nodes"] == []

    def test_dag_nodes_ccr_hash_matches_think_response(self, db_path):
        """I43-T4: dag.nodes[*].ccr_hash == think 응답의 ccr_hash 일치"""
        r = think(db_path, "s1", "n1", "Objective", PAYLOAD)
        think_hash = r["ccr_hash"]
        s = status(db_path, "s1")
        node_entry = next(n for n in s["dag"]["nodes"] if n["name"] == "n1")
        assert node_entry["ccr_hash"] == think_hash, (
            f"dag.nodes ccr_hash({node_entry['ccr_hash']}) != "
            f"think 응답 ccr_hash({think_hash})"
        )


# ---------------------------------------------------------------------------
# I44: _is_list_content `+` 불릿 지원
# ---------------------------------------------------------------------------

class TestIsListContentPlusBullet:
    """I44: `+` 불릿 프리픽스(GFM)를 리스트로 감지해야 한다."""

    def test_plus_bullets_three_lines_detected_as_list(self):
        """I44-T1: `+` 불릿 3줄 이상 → True"""
        text = "+ First item here\n+ Second item here\n+ Third item here"
        assert _is_list_content(text) is True, (
            "`+` 불릿 3줄이 리스트로 감지되지 않음"
        )

    def test_mixed_plus_minus_star_bullets(self):
        """I44-T2: `+`, `-`, `*` 혼합 3줄 → True"""
        text = "+ item one\n- item two\n* item three"
        assert _is_list_content(text) is True

    def test_minus_bullets_still_detected(self):
        """I44-T3: 기존 `-` 불릿 3줄 → True (회귀 방지)"""
        text = "- alpha\n- beta\n- gamma"
        assert _is_list_content(text) is True

    def test_plus_bullets_two_lines_not_list(self):
        """I44-T4: `+` 불릿 2줄 (<3) → False"""
        text = "+ item one\n+ item two"
        assert _is_list_content(text) is False

    def test_prose_not_detected_as_list(self):
        """I44-T5: 산문 3문장 → False"""
        text = "First sentence here.\nSecond sentence here.\nThird sentence here."
        assert _is_list_content(text) is False

    def test_plus_without_space_not_list(self):
        """I44-T6: `+item` (공백 없음) → False (정확한 GFM 패턴만 인정)"""
        text = "+item1\n+item2\n+item3"
        assert _is_list_content(text) is False


# ---------------------------------------------------------------------------
# I45: _compute_dag_health total_nodes
# ---------------------------------------------------------------------------

class TestDagHealthTotalNodes:
    """I45: dag_health에 total_nodes(COMPLETED 노드 수)가 포함되어야 한다."""

    def test_empty_session_total_nodes_zero(self, db_path):
        """I45-T1: 빈 세션 status → dag_health.total_nodes==0"""
        s = status(db_path, "empty_session")
        health = s["dag_health"]
        assert "total_nodes" in health, "dag_health에 total_nodes 키 없음"
        assert health["total_nodes"] == 0

    def test_single_completed_node(self, db_path):
        """I45-T2: COMPLETED 노드 1개 → total_nodes==1"""
        think(db_path, "s1", "n1", "Objective", PAYLOAD)
        s = status(db_path, "s1")
        assert s["dag_health"]["total_nodes"] == 1

    def test_three_completed_nodes(self, db_path):
        """I45-T3: COMPLETED 노드 3개 → total_nodes==3"""
        think(db_path, "s1", "n1", "Objective", PAYLOAD)
        think(db_path, "s1", "n2", "Hypothesis", PAYLOAD)
        think(db_path, "s1", "n3", "Evidence", PAYLOAD)
        s = status(db_path, "s1")
        assert s["dag_health"]["total_nodes"] == 3

    def test_invalidated_node_excluded_from_total(self, db_path):
        """I45-T4: think 2회 후 1개 invalidate → total_nodes==1 (INVALIDATED 제외)"""
        think(db_path, "s1", "n1", "Objective", PAYLOAD)
        think(db_path, "s1", "n2", "Hypothesis", PAYLOAD)
        invalidate(db_path, "s1", "n2")
        s = status(db_path, "s1")
        assert s["dag_health"]["total_nodes"] == 1, (
            f"INVALIDATED 노드가 total_nodes에 포함됨: {s['dag_health']['total_nodes']}"
        )

    def test_total_nodes_in_status_response(self, db_path):
        """I45-T5: status 응답의 dag_health에 total_nodes 키 존재"""
        think(db_path, "s1", "n1", "Objective", PAYLOAD)
        s = status(db_path, "s1")
        assert "total_nodes" in s["dag_health"]
