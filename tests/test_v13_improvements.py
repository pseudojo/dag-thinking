"""
dag-thinking v0.13 improvements — TDD RED phase
I31: whitespace-only payload validation
I32: idx_edges_child index
I33: _split_sentences ellipsis false-split fix
I34: edges loop → executemany + guard clarification
+ C33/C34/C37/C39/C40/C41 missing coverage
"""

import sqlite3

import pytest

from src.compressor import _TYPE_KEYWORDS, _score_sentence, _split_sentences, compress
from src.server import init_db
from tests.helpers import PAYLOAD, invalidate, status, think

# ---------------------------------------------------------------------------
# I31: whitespace-only payload 차단
# ---------------------------------------------------------------------------


class TestWhitespacePayloadValidation:
    """I31: _validate_think_inputs — 공백 전용 payload ValueError"""

    def test_whitespace_only_payload_raises(self, db_path):
        """T1: ' ' * 100 (공백 전용 100자) → ValueError"""
        with pytest.raises(ValueError, match="blank|whitespace"):
            think(db_path, "s1", "n", "Objective", " " * 100)

    def test_tab_newline_payload_raises(self, db_path):
        """T2: 탭+개행 혼합 공백 전용 → ValueError"""
        with pytest.raises(ValueError, match="blank|whitespace"):
            think(db_path, "s1", "n", "Objective", "\t\n  \t")

    def test_payload_exactly_79_chars_raises(self, db_path):
        """T3: 79자 정상 문자 payload → ValueError (80자 미만 경계값)"""
        with pytest.raises(ValueError):
            think(db_path, "s1", "n", "Objective", "x" * 79)

    def test_payload_exactly_80_chars_passes(self, db_path):
        """T4: 80자 payload → 정상 처리 (하한 경계값 통과)"""
        result = think(db_path, "s1", "n", "Objective", "x" * 80)
        assert result["status"] in ("created", "updated")

    def test_payload_exactly_1500_chars_passes(self, db_path):
        """T5: 1500자 payload → 정상 처리 (상한 경계값 통과)"""
        result = think(db_path, "s1", "n", "Objective", "x" * 1500)
        assert result["status"] in ("created", "updated")

    def test_payload_exactly_1501_chars_raises(self, db_path):
        """T6: 1501자 payload → ValueError"""
        with pytest.raises(ValueError):
            think(db_path, "s1", "n", "Objective", "x" * 1501)


# ---------------------------------------------------------------------------
# I32: node_name / depends_on 경계값 + idx_edges_child 인덱스
# ---------------------------------------------------------------------------


class TestBoundaryValidation:
    """I32 + 경계값: node_name 200/201자, depends_on 20/21개"""

    def test_node_name_exactly_200_chars_passes(self, db_path):
        """C46: node_name 200자 → 정상 처리"""
        result = think(db_path, "s1", "n" * 200, "Objective", PAYLOAD)
        assert result["status"] in ("created", "updated")

    def test_node_name_exactly_201_chars_raises(self, db_path):
        """C47: node_name 201자 → ValueError"""
        with pytest.raises(ValueError):
            think(db_path, "s1", "n" * 201, "Objective", PAYLOAD)

    def test_depends_on_exactly_20_passes(self, db_path):
        """C48: depends_on 20개 → 정상 처리 (상한 경계값 통과)"""
        # 부모 노드 1개 생성 (나머지는 존재하지 않아도 ValidationError 아님)
        think(db_path, "s1", "parent", "Objective", PAYLOAD)
        # depends_on에 존재하지 않는 이름 포함해도 ValidationError는 아님
        deps = [f"p{i}" for i in range(20)]
        # ValueError가 아닌 일반 처리 (없는 부모는 error로 포함됨)
        result = think(db_path, "s1", "child", "Hypothesis", PAYLOAD, depends_on=deps)
        assert result["status"] in ("created", "updated")

    def test_depends_on_exactly_21_raises(self, db_path):
        """C49: depends_on 21개 → ValueError"""
        with pytest.raises(ValueError):
            deps = [f"p{i}" for i in range(21)]
            think(db_path, "s1", "child", "Hypothesis", PAYLOAD, depends_on=deps)

    def test_idx_edges_child_exists(self, tmp_path):
        """C50: init_db() 후 idx_edges_child 인덱스 존재"""
        path = str(tmp_path / "idx_test.db")
        init_db(path)
        conn = sqlite3.connect(path)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_edges_child'"
        ).fetchone()
        conn.close()
        assert row is not None, "idx_edges_child 인덱스가 존재해야 함"


# ---------------------------------------------------------------------------
# I33: _split_sentences 줄임표 false-split 수정
# ---------------------------------------------------------------------------


class TestSplitSentencesEllipsis:
    """I33: _split_sentences — 연속 구두점(줄임표) 오분리 방지"""

    def test_ellipsis_not_split(self):
        """T9: 'Wait...really?' → 1개 문장 (줄임표 오분리 없음)"""
        result = _split_sentences("Wait...really?")
        assert len(result) == 1, f"줄임표를 문장 경계로 오인 분리: {result}"

    def test_ellipsis_with_real_sentence_boundary(self):
        """T10: 'No...really? Yes.' → 2개 문장 (공백 후 분리)"""
        result = _split_sentences("No...really? Yes.")
        assert len(result) == 2
        assert result[0] == "No...really?"
        assert result[1] == "Yes."

    def test_normal_split_preserved(self):
        """T11: 'Hello. World.' → 정상 분리 유지"""
        result = _split_sentences("Hello. World.")
        assert len(result) == 2
        assert result[0] == "Hello."
        assert result[1] == "World."

    def test_cjk_split_preserved(self):
        """T12: CJK 종결자 즉시 분리 유지"""
        result = _split_sentences("결론이다。다음은 단계다。")
        assert len(result) == 2
        assert "결론이다" in result[0]
        assert "다음은" in result[1]

    def test_single_sentence_no_split(self):
        """T13: 단일 문장 → 분리 없음"""
        result = _split_sentences("End!")
        assert result == ["End!"]


# ---------------------------------------------------------------------------
# I34: edges executemany + 가드 명확화
# ---------------------------------------------------------------------------


class TestEdgesExecutemany:
    """I34: executemany 최적화 + parent_context 가드 명확화"""

    def test_valid_parents_edges_created(self, db_path):
        """T14: 유효 부모 2개 → edges 2개 생성"""
        think(db_path, "s1", "a", "Objective", PAYLOAD)
        think(db_path, "s1", "b", "Hypothesis", PAYLOAD)
        think(db_path, "s1", "c", "Evidence", PAYLOAD, depends_on=["a", "b"])
        s = status(db_path, "s1")
        edges = s["dag"]["edges"]
        edge_pairs = {(e["parent"], e["child"]) for e in edges}
        assert ("a", "c") in edge_pairs
        assert ("b", "c") in edge_pairs

    def test_missing_parent_no_edge_no_error(self, db_path):
        """T15: 존재하지 않는 부모 포함 → 유효 부모만 엣지, 오류 없음"""
        think(db_path, "s1", "real", "Objective", PAYLOAD)
        result = think(
            db_path, "s1", "child", "Hypothesis", PAYLOAD, depends_on=["real", "nonexistent"]
        )
        assert result["status"] in ("created", "updated")
        s = status(db_path, "s1")
        edges = s["dag"]["edges"]
        edge_pairs = {(e["parent"], e["child"]) for e in edges}
        assert ("real", "child") in edge_pairs
        assert ("nonexistent", "child") not in edge_pairs

    def test_invalidated_parent_warning_no_edge(self, db_path):
        """T16: INVALIDATED 부모 → warning 포함, 엣지 생성됨 (기존 동작 유지)"""
        think(db_path, "s1", "inv", "Objective", PAYLOAD)
        invalidate(db_path, "s1", "inv")
        result = think(db_path, "s1", "child", "Hypothesis", PAYLOAD, depends_on=["inv"])
        assert "parent_context" in result
        ctx = result["parent_context"].get("inv", {})
        assert ctx.get("warning") or ctx.get("is_invalidated")


# ---------------------------------------------------------------------------
# C33/C34: thought_type 키워드 가중치
# ---------------------------------------------------------------------------


class TestThoughtTypeKeywords:
    """C33/C34: _score_sentence extra_keywords + compress 반환 타입"""

    EVIDENCE_SENTENCE = (
        "The data shows that measured performance metrics found during test "
        "revealed observed latency values with key results."
    )

    def test_score_with_evidence_keywords_higher(self):
        """C33: Evidence 키워드 포함 시 스코어가 base보다 높아야 함"""
        base_score = _score_sentence(self.EVIDENCE_SENTENCE, 0, 2)
        boosted_score = _score_sentence(
            self.EVIDENCE_SENTENCE, 0, 2, extra_keywords=_TYPE_KEYWORDS["Evidence"]
        )
        assert boosted_score > base_score, (
            f"Evidence 키워드 부스트 실패: base={base_score}, boosted={boosted_score}"
        )

    def test_compress_synthesis_returns_tuple(self):
        """C34: compress(text, 'Synthesis') → (str, str, int) 반환"""
        text = (
            "The overall conclusion integrates all findings. "
            "We combine evidence from multiple sources to reconcile the hypothesis. "
            "The summary is that the system requires a fundamental redesign. "
            "This synthesis represents the core result of our analysis phase. "
            "The final integration of all evidence points to a clear direction forward for "
            "the team."
        )
        result = compress(text, "Synthesis")
        assert isinstance(result, tuple) and len(result) == 3
        compressed, hash_val, tokens_saved = result
        assert isinstance(compressed, str)
        assert isinstance(hash_val, str) and len(hash_val) == 24
        assert isinstance(tokens_saved, int)


# ---------------------------------------------------------------------------
# C37/C39/C40/C41: context_pressure + dag_health
# ---------------------------------------------------------------------------


class TestContextPressureAndDagHealth:
    """C37/C39/C40/C41: 압박 경보 및 DAG 수렴 진단"""

    def test_pressure_medium_with_8_nodes(self, db_path):
        """C37: 8개 이상 노드 → context_pressure.level 'medium' 또는 'high'"""
        types = [
            "Objective",
            "Hypothesis",
            "Assumption",
            "Evidence",
            "Critique",
            "Synthesis",
            "Action",
            "Evidence",
        ]
        for i, t in enumerate(types):
            think(db_path, "pressure_sess", f"node_{i}", t, PAYLOAD)
        # 마지막 노드 응답에서 pressure 확인
        result = think(db_path, "pressure_sess", "node_8", "Hypothesis", PAYLOAD)
        assert result["context_pressure"]["level"] in ("medium", "high"), (
            f"8+ 노드임에도 level=low: {result['context_pressure']}"
        )

    def test_is_converging_with_synthesis_node(self, db_path):
        """C39: Synthesis COMPLETED 노드 존재 → is_converging == True"""
        think(db_path, "conv_sess", "obj", "Objective", PAYLOAD)
        think(db_path, "conv_sess", "syn", "Synthesis", PAYLOAD, depends_on=["obj"])
        s = status(db_path, "conv_sess")
        assert s["dag_health"]["is_converging"] is True

    def test_max_depth_with_chain(self, db_path):
        """C40: A→B→C 체인 → max_depth == 2"""
        think(db_path, "chain_sess", "a", "Objective", PAYLOAD)
        think(db_path, "chain_sess", "b", "Hypothesis", PAYLOAD, depends_on=["a"])
        think(db_path, "chain_sess", "c", "Evidence", PAYLOAD, depends_on=["b"])
        s = status(db_path, "chain_sess")
        assert s["dag_health"]["max_depth"] == 2, (
            f"A→B→C 체인의 max_depth가 2가 아님: {s['dag_health']['max_depth']}"
        )

    def test_orphan_nodes_detected(self, db_path):
        """C41: 연결 없는 2개 노드 → orphan_nodes 비-빈 리스트"""
        think(db_path, "orphan_sess", "isolated_a", "Objective", PAYLOAD)
        think(db_path, "orphan_sess", "isolated_b", "Hypothesis", PAYLOAD)
        # depends_on 없이 생성 → 엣지 없음 → 고립 노드
        s = status(db_path, "orphan_sess")
        assert len(s["dag_health"]["orphan_nodes"]) > 0, (
            f"고립 노드가 감지되지 않음: {s['dag_health']['orphan_nodes']}"
        )
