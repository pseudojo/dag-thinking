"""v0.18 개선 테스트 — I49·I50·I51·I52·I53"""

import pytest

from src.compressor import _split_sentences
from tests.helpers import status, think

# ── I49: _split_sentences 약어 false-split 수정 ──────────────────────────────


class TestSplitSentencesAbbreviation:
    """I49: 약어(Dr., e.g., U.S. 등) 뒤 공백이 문장 경계로 오인 분리되지 않아야 한다."""

    def test_normal_lowercase_split(self):
        """T1: 소문자 종결 문장 정상 분리."""
        result = _split_sentences("Hello world. Next sentence.")
        assert result == ["Hello world.", "Next sentence."]

    def test_exclamation_split(self):
        """T2: 느낌표 종결 정상 분리."""
        result = _split_sentences("It works! Great.")
        assert result == ["It works!", "Great."]

    def test_dr_abbreviation_not_split(self):
        """T3: Dr. 약어 — 단일 문장으로 유지."""
        result = _split_sentences("Dr. Smith found the error.")
        assert result == ["Dr. Smith found the error."]

    def test_eg_abbreviation_not_split(self):
        """T4: e.g. 약어 — 단일 문장으로 유지."""
        result = _split_sentences("Use e.g. this pattern.")
        assert result == ["Use e.g. this pattern."]

    def test_us_abbreviation_not_split(self):
        """T5: U.S. 약어 — 단일 문장으로 유지."""
        result = _split_sentences("U.S. policy changed today.")
        assert result == ["U.S. policy changed today."]

    def test_abbreviation_and_sentence_boundary_coexist(self):
        """T6: 약어 포함 문장 + 정상 문장 경계 공존."""
        result = _split_sentences("Dr. Smith said hello. He left.")
        assert result == ["Dr. Smith said hello.", "He left."]

    def test_double_exclamation_compound_terminator(self):
        """T7: !! 복합 종결자 — 경계 인식 (I48 회귀 방지)."""
        result = _split_sentences("Hello world!! How are you")
        assert result == ["Hello world!!", "How are you"]

    def test_question_exclamation_compound_terminator(self):
        """T8: ?! 복합 종결자 — 경계 인식."""
        result = _split_sentences("Really?! Yes.")
        assert result == ["Really?!", "Yes."]

    def test_ellipsis_not_split(self):
        """T9: 줄임표 — 경계로 인식하지 않음 (I38/I48 회귀 방지)."""
        result = _split_sentences("Wait... Are you sure?")
        assert result == ["Wait... Are you sure?"]

    def test_cjk_immediate_split(self):
        """T10: CJK 종결자 즉시 분리 (I12 회귀 방지)."""
        result = _split_sentences("안녕하세요。잘 지내세요。")
        assert result == ["안녕하세요。", "잘 지내세요。"]

    def test_empty_string_returns_empty_list(self):
        """T11: 빈 문자열 → 빈 리스트."""
        assert _split_sentences("") == []

    def test_single_sentence_no_terminator(self):
        """T12: 종결자 없는 단일 문장 → 그대로 반환."""
        result = _split_sentences("No period here")
        assert result == ["No period here"]

    def test_vs_abbreviation_not_split(self):
        """T13: vs. 약어 — 단일 문장으로 유지."""
        result = _split_sentences("Python vs. JavaScript is debated.")
        assert result == ["Python vs. JavaScript is debated."]

    def test_fig_abbreviation_not_split(self):
        """T14: Fig. 약어 — 단일 문장으로 유지."""
        result = _split_sentences("See Fig. 3 for details.")
        assert result == ["See Fig. 3 for details."]


# ── I50: TOCTOU cycle check 트랜잭션 내부 이동 ───────────────────────────────


class TestCycleCheckInsideTransaction:
    """I50: cycle check가 with conn: 트랜잭션 내부에서 실행됨을 검증한다."""

    def test_no_depends_on_creates_node(self, db_path):
        """T1: depends_on 없는 노드 정상 생성."""
        result = think(db_path, "s1", "n1", "Objective")
        assert result["status"] == "created"

    def test_with_valid_depends_on_creates_node(self, db_path):
        """T2: 사이클 없는 depends_on → 정상 생성 + parent_context 포함."""
        think(db_path, "s1", "n1", "Objective")
        result = think(db_path, "s1", "n2", "Hypothesis", depends_on=["n1"])
        assert result["status"] == "created"
        assert "parent_context" in result
        assert "n1" in result["parent_context"]

    def test_direct_cycle_raises_value_error(self, db_path):
        """T3: A→B 후 B→A 시도 → ValueError(Cycle detected)."""
        think(db_path, "s1", "n1", "Objective")
        think(db_path, "s1", "n2", "Hypothesis", depends_on=["n1"])
        with pytest.raises(ValueError, match="[Cc]ycle"):
            think(db_path, "s1", "n1", "Objective", depends_on=["n2"])

    def test_self_reference_raises_value_error(self, db_path):
        """T4: 자기 참조 depends_on=[self] → ValueError."""
        with pytest.raises(ValueError, match="[Cc]ycle"):
            think(db_path, "s1", "n1", "Objective", depends_on=["n1"])

    def test_transitive_cycle_raises_value_error(self, db_path):
        """T5: A→B→C 후 C→A 시도 → ValueError."""
        think(db_path, "s1", "n1", "Objective")
        think(db_path, "s1", "n2", "Hypothesis", depends_on=["n1"])
        think(db_path, "s1", "n3", "Evidence", depends_on=["n2"])
        with pytest.raises(ValueError, match="[Cc]ycle"):
            think(db_path, "s1", "n1", "Objective", depends_on=["n3"])

    def test_cycle_attempt_does_not_create_node(self, db_path):
        """T6: 사이클 시도 거부 후 DB 노드 수 변화 없음."""
        think(db_path, "s1", "n1", "Objective")
        think(db_path, "s1", "n2", "Hypothesis", depends_on=["n1"])
        with pytest.raises(ValueError):
            think(db_path, "s1", "n3", "Evidence", depends_on=["n3"])
        s = status(db_path, "s1")
        node_names = [n["name"] for n in s["dag"]["nodes"]]
        assert "n3" not in node_names, "사이클 거부 후 n3가 DB에 생성되면 안 됨"

    def test_empty_depends_on_skips_cycle_check(self, db_path):
        """T7: depends_on=[] → 사이클 체크 스킵, 정상 생성 (I40 유지)."""
        result = think(db_path, "s1", "n1", "Objective", depends_on=[])
        assert result["status"] == "created"

    def test_nonexistent_parent_in_parent_context_error(self, db_path):
        """T8: 존재하지 않는 부모 → parent_context에 error 키 포함."""
        result = think(db_path, "s1", "n1", "Objective", depends_on=["ghost"])
        assert "parent_context" in result
        assert "error" in result["parent_context"]["ghost"]


# ── I51: node_name 공백 정규화 ──────────────────────────────────────────────


class TestNodeNameWhitespaceNormalization:
    """I51: node_name 선행/후행 공백이 DB 저장 전에 제거되어야 한다."""

    def test_normal_name_unchanged(self, db_path):
        """T1: 공백 없는 이름 → 그대로 반환."""
        result = think(db_path, "s1", "normal", "Objective")
        assert result["node"] == "normal"

    def test_leading_space_stripped(self, db_path):
        """T2: 선행 공백 제거."""
        result = think(db_path, "s1", " padded", "Objective")
        assert result["node"] == "padded"

    def test_trailing_space_stripped(self, db_path):
        """T3: 후행 공백 제거."""
        result = think(db_path, "s1", "padded ", "Objective")
        assert result["node"] == "padded"

    def test_both_sides_stripped(self, db_path):
        """T4: 양쪽 공백 제거."""
        result = think(db_path, "s1", "  both  ", "Objective")
        assert result["node"] == "both"

    def test_padded_node_invalidated_by_clean_name(self, db_path):
        """T5: 공백 포함 이름으로 생성 후 깨끗한 이름으로 invalidate 성공."""
        think(db_path, "s1", " mynode ", "Objective")
        from src.server import call_dag_thinking

        result = call_dag_thinking(
            db_path=db_path,
            action="invalidate",
            session_id="s1",
            target_node="mynode",
        )
        assert "mynode" in result["invalidated"]

    def test_padded_parent_in_depends_on_resolved(self, db_path):
        """T6: 부모 이름 공백 포함 생성, depends_on 참조 시 strip 후 매칭."""
        think(db_path, "s1", " parent ", "Objective")
        result = think(db_path, "s1", "child", "Hypothesis", depends_on=[" parent "])
        assert "parent_context" in result
        assert "parent" in result["parent_context"]

    def test_whitespace_only_node_name_raises(self, db_path):
        """T7: 공백 전용 node_name → ValueError."""
        with pytest.raises(ValueError):
            think(db_path, "s1", "   ", "Objective")

    def test_depends_on_items_stripped(self, db_path):
        """T8: depends_on 항목 공백 strip 후 정상 엣지 생성."""
        think(db_path, "s1", "n1", "Objective")
        result = think(db_path, "s1", "n2", "Hypothesis", depends_on=[" n1 "])
        assert "parent_context" in result
        assert "n1" in result["parent_context"]


# ── I52: _action_restore 삭제된 노드 경고 ──────────────────────────────────


class TestRestoreDeletedNodeWarning:
    """I52: status=NULL(삭제된 노드) 복원 시 warning 키를 포함해야 한다."""

    def test_normal_restore_no_warning(self, db_path):
        """T1: COMPLETED 노드 정상 복원 — warning 없음."""
        from src.server import call_dag_thinking

        r = think(db_path, "s1", "n1", "Objective")
        h = r.get("ccr_hash")
        if h is None:
            pytest.skip("passthrough (no compression) — hash not available")
        result = call_dag_thinking(db_path=db_path, action="restore", session_id="s1", ccr_hash=h)
        assert "original_payload" in result
        assert "warning" not in result

    def test_invalidated_node_restore_has_warning(self, db_path):
        """T2: INVALIDATED 노드 복원 → warning 포함 (기존 동작 회귀 방지)."""
        from src.server import call_dag_thinking

        r = think(db_path, "s1", "n1", "Objective")
        h = r.get("ccr_hash")
        if h is None:
            pytest.skip("passthrough — no ccr_hash")
        call_dag_thinking(db_path=db_path, action="invalidate", session_id="s1", target_node="n1")
        result = call_dag_thinking(db_path=db_path, action="restore", session_id="s1", ccr_hash=h)
        assert "warning" in result

    def test_deleted_node_restore_has_warning(self, db_path):
        """T3: nodes 행 없는(삭제된) ccr_hash 복원 → warning 키 + 'deleted' 텍스트."""
        import contextlib
        import sqlite3

        from src.server import call_dag_thinking

        # ccr_store에 직접 삽입 — 대응하는 nodes 행 없음 (삭제 시뮬레이션)
        with contextlib.closing(sqlite3.connect(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            # 세션 생성
            call_dag_thinking(db_path=db_path, action="status", session_id="s1")
            conn.execute(
                "INSERT INTO ccr_store (hash, session_id, node_name, original) VALUES (?, ?, ?, ?)",
                ("deadbeef000000000000000a", "s1", "ghost_node", "original text"),
            )
            conn.commit()
        result = call_dag_thinking(
            db_path=db_path,
            action="restore",
            session_id="s1",
            ccr_hash="deadbeef000000000000000a",
        )
        assert "warning" in result
        assert "deleted" in result["warning"].lower()

    def test_invalid_hash_raises(self, db_path):
        """T4: 없는 hash → ValueError."""
        from src.server import call_dag_thinking

        call_dag_thinking(db_path=db_path, action="status", session_id="s1")
        with pytest.raises(ValueError):
            call_dag_thinking(
                db_path=db_path, action="restore", session_id="s1", ccr_hash="no_such_hash"
            )

    def test_none_hash_returns_restorable_nodes(self, db_path):
        """T5: ccr_hash=None → restorable_nodes 키 반환."""
        from src.server import call_dag_thinking

        think(db_path, "s1", "n1", "Objective")
        result = call_dag_thinking(db_path=db_path, action="restore", session_id="s1")
        assert "restorable_nodes" in result


# ── I53: _cascade_invalidate 개선 ──────────────────────────────────────────


class TestCascadeInvalidateImproved:
    """I53: _cascade_invalidate가 edges_graph 수신 및 신규 무효화 노드만 반환해야 한다."""

    def _setup_chain(self, db_path):
        """A→B→C 체인 생성 후 (conn, session_id) 반환."""
        think(db_path, "s1", "A", "Objective")
        think(db_path, "s1", "B", "Hypothesis", depends_on=["A"])
        think(db_path, "s1", "C", "Evidence", depends_on=["B"])

    def test_simple_chain_all_newly_invalidated(self, db_path):
        """T1: A→B→C, invalidate A → A·B·C 모두 신규 무효화."""
        from src.server import call_dag_thinking

        self._setup_chain(db_path)
        result = call_dag_thinking(
            db_path=db_path, action="invalidate", session_id="s1", target_node="A"
        )
        assert sorted(result["invalidated"]) == ["A", "B", "C"]

    def test_already_invalidated_excluded(self, db_path):
        """T2: B가 이미 INVALIDATED인 상태에서 A 무효화 → B는 newly에 포함되지 않음."""
        import contextlib

        from src.server import _cascade_invalidate, _db, call_dag_thinking

        self._setup_chain(db_path)
        # B를 먼저 무효화
        call_dag_thinking(db_path=db_path, action="invalidate", session_id="s1", target_node="B")

        with contextlib.closing(_db(db_path)) as conn:
            newly = _cascade_invalidate(conn, "s1", "A")
        # B는 이미 INVALIDATED → newly에 없어야 함
        assert "B" not in newly
        assert "A" in newly

    def test_edges_graph_provided_same_result(self, db_path):
        """T3: edges_graph 직접 제공 시 동일 결과."""
        import contextlib

        from src.server import _cascade_invalidate, _db, _ensure_session, _load_forward_edges

        self._setup_chain(db_path)

        with contextlib.closing(_db(db_path)) as conn:
            with conn:
                _ensure_session(conn, "s1")
            graph = _load_forward_edges(conn, "s1")
            newly = _cascade_invalidate(conn, "s1", "A", edges_graph=graph)
        assert sorted(newly) == ["A", "B", "C"]

    def test_leaf_node_only_itself(self, db_path):
        """T4: 자식 없는 리프 노드 → 자기 자신만 반환."""
        import contextlib

        from src.server import _cascade_invalidate, _db, _ensure_session

        self._setup_chain(db_path)

        with contextlib.closing(_db(db_path)) as conn:
            with conn:
                _ensure_session(conn, "s1")
            newly = _cascade_invalidate(conn, "s1", "C")
        assert newly == ["C"]

    def test_nonexistent_node_returns_empty(self, db_path):
        """T5: DB에 없는 노드 → []."""
        import contextlib

        from src.server import _cascade_invalidate, _db, _ensure_session

        with contextlib.closing(_db(db_path)) as conn:
            with conn:
                _ensure_session(conn, "s1")
            result = _cascade_invalidate(conn, "s1", "ghost")
        assert result == []

    def test_all_already_invalidated_returns_empty(self, db_path):
        """T6: 전체 이미 INVALIDATED → 빈 리스트."""
        import contextlib

        from src.server import _cascade_invalidate, _db, _ensure_session, call_dag_thinking

        self._setup_chain(db_path)
        # 전체 무효화
        call_dag_thinking(db_path=db_path, action="invalidate", session_id="s1", target_node="A")

        with contextlib.closing(_db(db_path)) as conn:
            with conn:
                _ensure_session(conn, "s1")
            newly = _cascade_invalidate(conn, "s1", "A")
        assert newly == []
