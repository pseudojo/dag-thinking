"""action='think' 행위 테스트 — call_dag_thinking 공개 디스패처 경유.

PLAN.md §3 think 명세 + §8 체크리스트 C03~C09, C26~C37, C42~C49, C53, BUG-1 커버.
"""

import re

import pytest

from tests.helpers import PAYLOAD, invalidate, status, think


class TestThinkBasics:
    def test_create_node_response_shape(self, db_path):
        """C03: 기본 생성 — created, ccr_hash 24-hex, thought_type 에코, parent_context 없음."""
        r = think(db_path, "s1", "define_problem", "Objective")
        assert r["status"] == "created"
        assert r["node"] == "define_problem"
        assert r["thought_type"] == "Objective"
        assert re.fullmatch(r"[0-9a-f]{24}", r["ccr_hash"])
        assert "parent_context" not in r

    def test_recreate_same_node_is_updated(self, db_path):
        """동일 이름 재생성 → status='updated'."""
        think(db_path, "s1", "n1", "Objective")
        r = think(db_path, "s1", "n1", "Hypothesis")
        assert r["status"] == "updated"
        assert r["thought_type"] == "Hypothesis"

    def test_node_name_is_stripped(self, db_path):
        """I51: node_name 앞뒤 공백 정규화."""
        r = think(db_path, "s1", "  spaced  ", "Objective")
        assert r["node"] == "spaced"

    def test_note_none_is_tolerated(self, db_path):
        """I46: note=None → 빈 문자열로 처리, 정상 생성."""
        r = think(db_path, "s1", "n1", "Objective", note=None)
        assert r["status"] == "created"


class TestThinkValidation:
    def test_payload_79_chars_rejected(self, db_path):
        """C07/C43: 80자 미만 경계값."""
        with pytest.raises(ValueError, match="80"):
            think(db_path, "s1", "n1", "Objective", payload="x" * 79)

    def test_payload_80_chars_accepted(self, db_path):
        """C44: 정확히 80자 통과."""
        assert think(db_path, "s1", "n1", "Objective", payload="x" * 80)["status"] == "created"

    def test_payload_1500_chars_accepted(self, db_path):
        """C45: 정확히 1500자 통과."""
        assert think(db_path, "s1", "n1", "Objective", payload="y" * 1500)["status"] == "created"

    def test_payload_1501_chars_rejected(self, db_path):
        """C08: 1500자 초과."""
        with pytest.raises(ValueError, match="1500"):
            think(db_path, "s1", "n1", "Objective", payload="y" * 1501)

    def test_whitespace_only_payload_rejected(self, db_path):
        """C42/I31: 공백 전용 payload는 길이를 충족해도 거부."""
        with pytest.raises(ValueError):
            think(db_path, "s1", "n1", "Objective", payload=" " * 100)

    def test_payload_none_rejected(self, db_path):
        """payload 미제공(None) → ValueError (helper는 None을 치환하므로 직접 호출)."""
        from src.actions import call_dag_thinking

        with pytest.raises(ValueError, match="payload"):
            call_dag_thinking(
                db_path=db_path,
                action="think",
                session_id="s1",
                node_name="n1",
                thought_type="Objective",
                payload=None,
            )

    def test_blank_node_name_rejected(self, db_path):
        """P3-12: 공백/탭/개행 node_name 거부."""
        for bad in ("", "   ", "\t\n"):
            with pytest.raises(ValueError, match="node_name"):
                think(db_path, "s1", bad, "Objective")

    def test_node_name_200_ok_201_rejected(self, db_path):
        """C46/C47: node_name 길이 경계."""
        assert think(db_path, "s1", "n" * 200, "Objective")["status"] == "created"
        with pytest.raises(ValueError, match="node_name"):
            think(db_path, "s1", "n" * 201, "Objective")

    def test_invalid_thought_type_rejected(self, db_path):
        """잘못된 thought_type → 유효 목록 안내."""
        with pytest.raises(ValueError, match="thought_type"):
            think(db_path, "s1", "n1", "Guess")

    def test_depends_on_20_ok_21_rejected(self, db_path):
        """C48/C49/I17: depends_on 개수 경계."""
        for i in range(21):
            think(db_path, "s1", f"p{i}", "Evidence")
        parents_20 = [f"p{i}" for i in range(20)]
        assert think(db_path, "s1", "child_a", "Synthesis", depends_on=parents_20)
        parents_21 = [f"p{i}" for i in range(21)]
        with pytest.raises(ValueError, match="depends_on"):
            think(db_path, "s1", "child_b", "Synthesis", depends_on=parents_21)

    def test_note_500_ok_501_rejected(self, db_path):
        """I36: note 길이 경계."""
        assert think(db_path, "s1", "n1", "Objective", note="z" * 500)["status"] == "created"
        with pytest.raises(ValueError, match="note"):
            think(db_path, "s1", "n2", "Objective", note="z" * 501)


class TestParentContext:
    def test_parent_context_attached(self, db_path):
        """C04/C05: depends_on → parent_context에 압축 payload 자동 첨부."""
        think(db_path, "s1", "root", "Objective")
        r = think(db_path, "s1", "child", "Hypothesis", depends_on=["root"])
        ctx = r["parent_context"]["root"]
        assert ctx["thought_type"] == "Objective"
        assert re.fullmatch(r"[0-9a-f]{24}", ctx["ccr_hash"])
        assert len(ctx["payload"]) <= len(PAYLOAD)
        assert ctx["is_compressed"] == (ctx["payload"] != PAYLOAD)

    def test_ghost_parent_yields_error_entry_and_no_edge(self, db_path):
        """P1-2: 미존재 부모 → error 엔트리 + 엣지 미생성."""
        r = think(db_path, "s1", "child", "Hypothesis", depends_on=["ghost"])
        assert "error" in r["parent_context"]["ghost"]
        assert status(db_path, "s1")["dag"]["edges"] == []

    def test_mixed_valid_and_ghost_parents(self, db_path):
        """P1-2: 유효+미존재 혼합 → 유효한 엣지만 생성."""
        think(db_path, "s1", "real", "Objective")
        think(db_path, "s1", "child", "Hypothesis", depends_on=["real", "ghost"])
        edges = status(db_path, "s1")["dag"]["edges"]
        assert edges == [{"parent": "real", "child": "child"}]

    def test_invalidated_parent_warning(self, db_path):
        """C06: INVALIDATED 부모 → warning + is_invalidated 플래그."""
        think(db_path, "s1", "root", "Objective")
        invalidate(db_path, "s1", "root")
        r = think(db_path, "s1", "child", "Hypothesis", depends_on=["root"])
        ctx = r["parent_context"]["root"]
        assert ctx["is_invalidated"] is True
        assert "INVALIDATED" in ctx["warning"]

    def test_duplicate_depends_on_creates_single_edge(self, db_path):
        """C53/I29: depends_on 중복·공백 변형 → 엣지 1개."""
        think(db_path, "s1", "root", "Objective")
        think(db_path, "s1", "child", "Hypothesis", depends_on=["root", " root ", "root"])
        edges = status(db_path, "s1")["dag"]["edges"]
        assert edges == [{"parent": "root", "child": "child"}]

    def test_outgoing_edges_survive_node_update(self, db_path):
        """R-EDGE/P2-3: 노드 재생성 시 자식으로 향하는 엣지 보존."""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        think(db_path, "s1", "a", "Objective")  # a 업데이트
        edges = status(db_path, "s1")["dag"]["edges"]
        assert {"parent": "a", "child": "b"} in edges


class TestCycleDetection:
    def test_self_reference_rejected(self, db_path):
        """IC02: A depends_on A."""
        think(db_path, "s1", "a", "Objective")
        with pytest.raises(ValueError, match="[Cc]ycle"):
            think(db_path, "s1", "a", "Objective", depends_on=["a"])

    def test_direct_cycle_rejected(self, db_path):
        """IC01: A→B 존재 시 A depends_on B 거부."""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        with pytest.raises(ValueError, match="[Cc]ycle"):
            think(db_path, "s1", "a", "Objective", depends_on=["b"])

    def test_transitive_cycle_rejected(self, db_path):
        """IC03: 3-hop 전이 사이클."""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        think(db_path, "s1", "c", "Evidence", depends_on=["b"])
        with pytest.raises(ValueError, match="[Cc]ycle"):
            think(db_path, "s1", "a", "Objective", depends_on=["c"])

    def test_diamond_structure_allowed(self, db_path):
        """IC04: 다이아몬드(A→B, A→C, B/C→D)는 사이클이 아님."""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        think(db_path, "s1", "c", "Hypothesis", depends_on=["a"])
        r = think(db_path, "s1", "d", "Synthesis", depends_on=["b", "c"])
        assert r["status"] == "created"


class TestNextHint:
    EXPECTATIONS = {
        "Objective": ("Hypothesis", "Assumption"),
        "Hypothesis": ("Evidence", "Assumption"),
        "Assumption": ("Evidence", "Critique"),
        "Evidence": ("Synthesis", "Critique"),
        "Critique": ("Synthesis",),
        "Synthesis": ("Action", "status"),
        "Action": ("status()",),
    }

    @pytest.mark.parametrize("ttype,keywords", sorted(EXPECTATIONS.items()))
    def test_next_hint_guides_by_type(self, db_path, ttype, keywords):
        """C26~C32: thought_type별 동적 next_hint."""
        hint = think(db_path, "s1", f"n_{ttype}", ttype)["next_hint"]
        assert any(k in hint for k in keywords), f"{ttype} hint에 {keywords} 없음: {hint}"


class TestCompressionMetrics:
    def test_session_total_accumulates(self, db_path):
        """IC05/IC06: session_total_saved 누적."""
        r1 = think(db_path, "s1", "n1", "Objective")
        r2 = think(db_path, "s1", "n2", "Hypothesis")
        c1, c2 = r1["compression"], r2["compression"]
        assert c1["session_total_saved"] == c1["tokens_saved"]
        assert c2["session_total_saved"] == c1["tokens_saved"] + c2["tokens_saved"]

    def test_no_double_count_on_recreate(self, db_path):
        """BUG-1: 동일 payload 재생성 → session total 불변."""
        r1 = think(db_path, "s1", "n1", "Objective")
        r2 = think(db_path, "s1", "n1", "Objective")
        assert r2["compression"]["session_total_saved"] == r1["compression"]["session_total_saved"]

    def test_short_payload_zero_saved(self, db_path):
        """C10: 100자 미만 payload → tokens_saved=0 (passthrough)."""
        r = think(db_path, "s1", "n1", "Objective", payload="p" * 85)
        assert r["compression"]["tokens_saved"] == 0


class TestContextPressure:
    def _fill(self, db_path, sid, count, prefix="node"):
        last = None
        for i in range(count):
            last = think(db_path, sid, f"{prefix}{i}", "Evidence")
        return last

    def test_first_node_low(self, db_path):
        """C36: 첫 노드 → level=low, node_count=1."""
        cp = think(db_path, "s1", "n0", "Objective")["context_pressure"]
        assert cp == {"level": "low", "node_count": 1, "hint": cp["hint"]}
        assert cp["hint"]

    def test_boundary_8_nodes_medium(self, db_path):
        """C37: 8번째 노드 → medium (경계값)."""
        r = self._fill(db_path, "s1", 8)
        assert r["context_pressure"]["level"] == "medium"
        assert r["context_pressure"]["node_count"] == 8

    def test_boundary_15_nodes_high(self, db_path):
        """15번째 노드 → high (경계값)."""
        r = self._fill(db_path, "s1", 15)
        assert r["context_pressure"]["level"] == "high"

    def test_invalidated_nodes_excluded(self, db_path):
        """P3-9: INVALIDATED 노드는 node_count에서 제외."""
        self._fill(db_path, "s1", 8)
        invalidate(db_path, "s1", "node0")
        invalidate(db_path, "s1", "node1")
        r = think(db_path, "s1", "fresh", "Evidence")
        assert r["context_pressure"]["node_count"] == 7
        assert r["context_pressure"]["level"] == "low"
