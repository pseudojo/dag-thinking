"""
v0.8 improvements — RED phase tests.

Covers:
  I09: _compute_context_pressure — with conn: 블록 밖으로 이동 (기능 회귀 검증)
  I10: _compute_dag_health — INVALIDATED 노드를 경유하는 엣지를 BFS/고립 계산에서 제외
  I11: _compress_prose 유니코드 문장 구분자 지원 (_split_sentences 함수 추출)
"""

import pytest

from tests.helpers import invalidate, status, think

# I11 임포트 — _split_sentences 존재하지 않으면 RED 단계에서 ImportError
try:
    from src.compressor import _split_sentences, compress
    _HAS_SPLIT = True
except ImportError:
    _HAS_SPLIT = False
    from src.compressor import compress


PAYLOAD = (
    "The key finding from this analysis is that the current architecture has a critical bottleneck "
    "in the data pipeline. The assumption is that horizontal scaling will resolve the throughput issue. "
    "Evidence from load tests shows that latency doubles beyond 500 concurrent connections. "
    "Therefore, the conclusion is to implement a message queue to decouple producers from consumers. "
    "This result must be addressed before the next production release to avoid system failure."
)

CJK_PAYLOAD = (
    "이것은 목표 문장이다。 가설을 검증해야 한다。 "
    "데이터가 필요하다。 증거를 수집했다。 "
    "결론을 도출하겠다。 행동 계획이 필요하다。 "
    "최종 결론은 이것이다。 다음 단계는 실행이다。"
)


# ---------------------------------------------------------------------------
# I09: context_pressure 회귀 검증 (기능 변경 없음 — 리팩토링 안전망)
# ---------------------------------------------------------------------------

class TestI09ContextPressureRegression:
    """I09: _compute_context_pressure 호출 위치 이동 후 기능 동일성 보장."""

    def test_think_response_includes_context_pressure(self, db_path):
        """I09-1: think 응답에 context_pressure 필드 존재."""
        r = think(db_path, "s1", "node_a", "Objective")
        assert "context_pressure" in r
        cp = r["context_pressure"]
        assert "level" in cp
        assert "node_count" in cp
        assert "hint" in cp

    def test_context_pressure_node_count_reflects_created_node(self, db_path):
        """I09-2: node_count가 방금 생성된 노드를 포함 — with conn: 블록 밖에서도 정확."""
        r1 = think(db_path, "s1", "node_a", "Objective")
        assert r1["context_pressure"]["node_count"] == 1

        r2 = think(db_path, "s1", "node_b", "Hypothesis", depends_on=["node_a"])
        assert r2["context_pressure"]["node_count"] == 2

    def test_context_pressure_level_thresholds(self, db_path):
        """I09-3: level 임계값 (low/medium/high) 정확성."""
        # 첫 노드 → low
        r = think(db_path, "s1", "n1", "Objective")
        assert r["context_pressure"]["level"] == "low"


# ---------------------------------------------------------------------------
# I10: _compute_dag_health — INVALIDATED 엣지 BFS 제외
# ---------------------------------------------------------------------------

class TestI10DagHealthInvalidatedFilter:
    """I10: INVALIDATED 노드를 경유하는 엣지가 max_depth / orphan_nodes 계산을 오염하는 버그 수정."""

    def test_max_depth_excludes_path_through_invalidated_node(self, db_path):
        """I10-1: A→B→C, B invalidate(cascade: C도) → D 단독 생성.

        완료 노드: {A, D}
        엣지: A→B (B=INVALIDATED), B→C (둘 다 INVALIDATED) — 모두 제외 대상

        After fix: max_depth == 0  (COMPLETED 전용 서브그래프에 엣지 없음)
        Before fix: max_depth == 2  (A→B→C BFS가 INVALIDATED 경유)
        """
        think(db_path, "s1", "A", "Objective")
        think(db_path, "s1", "B", "Hypothesis", depends_on=["A"])
        think(db_path, "s1", "C", "Evidence", depends_on=["B"])
        # B invalidate → B, C 모두 INVALIDATED (cascade)
        invalidate(db_path, "s1", "B")
        # D: 독립 COMPLETED 노드 추가 (orphan 기준 2개 이상 충족)
        think(db_path, "s1", "D", "Assumption")

        s = status(db_path, "s1")
        health = s["dag_health"]
        assert health["max_depth"] == 0, (
            f"max_depth should be 0 (no COMPLETED edges), got {health['max_depth']}. "
            f"This indicates INVALIDATED edges are still used in BFS."
        )

    def test_orphan_nodes_excludes_invalidated_connected_node(self, db_path):
        """I10-2: A→B (B=INVALIDATED) + D 단독 → A와 D 모두 orphan.

        After fix: orphan_nodes == ["A", "D"]
        Before fix: orphan_nodes == ["D"] (A는 A→B 엣지 때문에 'connected'로 오분류)
        """
        think(db_path, "s1", "A", "Objective")
        think(db_path, "s1", "B", "Hypothesis", depends_on=["A"])
        think(db_path, "s1", "C", "Evidence", depends_on=["B"])
        invalidate(db_path, "s1", "B")  # B, C → INVALIDATED; A stays COMPLETED
        think(db_path, "s1", "D", "Assumption")  # standalone COMPLETED

        s = status(db_path, "s1")
        health = s["dag_health"]
        orphans = health["orphan_nodes"]
        assert "A" in orphans, (
            f"A should be an orphan (its only edge leads to INVALIDATED B), "
            f"got orphan_nodes={orphans}"
        )
        assert "D" in orphans, (
            f"D should be an orphan (no edges), got orphan_nodes={orphans}"
        )

    def test_fully_completed_chain_max_depth_regression(self, db_path):
        """I10-3: 회귀 — A→B→C 모두 COMPLETED → max_depth == 2."""
        think(db_path, "s1", "A", "Objective")
        think(db_path, "s1", "B", "Hypothesis", depends_on=["A"])
        think(db_path, "s1", "C", "Evidence", depends_on=["B"])

        s = status(db_path, "s1")
        health = s["dag_health"]
        assert health["max_depth"] == 2, (
            f"Regression: COMPLETED chain A→B→C should have max_depth=2, got {health['max_depth']}"
        )

    def test_fully_completed_chain_no_orphans_regression(self, db_path):
        """I10-4: 회귀 — A→B→C 모두 COMPLETED → orphan_nodes == []."""
        think(db_path, "s1", "A", "Objective")
        think(db_path, "s1", "B", "Hypothesis", depends_on=["A"])
        think(db_path, "s1", "C", "Evidence", depends_on=["B"])

        s = status(db_path, "s1")
        health = s["dag_health"]
        assert health["orphan_nodes"] == [], (
            f"Regression: fully connected chain should have no orphans, "
            f"got {health['orphan_nodes']}"
        )


# ---------------------------------------------------------------------------
# I11: _split_sentences — 유니코드 문장 구분자 지원
# ---------------------------------------------------------------------------

class TestI11SplitSentences:
    """I11: _split_sentences 함수 추출 + 유니코드 (。！？) 문장 구분자 지원."""

    def test_split_sentences_is_importable(self):
        """I11-1: _split_sentences가 src.compressor에서 직접 임포트 가능."""
        assert _HAS_SPLIT, (
            "_split_sentences is not importable from src.compressor. "
            "This function must be extracted from _compress_prose."
        )

    @pytest.mark.skipif(not _HAS_SPLIT, reason="_split_sentences not yet implemented")
    def test_cjk_period_splits_sentences(self):
        """I11-2: 한중일 마침표(。) + 공백으로 문장 분리."""
        text = "결론은 A다。 하지만 B도 있다。 세 번째 문장이다。"
        sentences = _split_sentences(text)
        assert len(sentences) == 3, (
            f"CJK 。 should split into 3 sentences, got {len(sentences)}: {sentences}"
        )

    @pytest.mark.skipif(not _HAS_SPLIT, reason="_split_sentences not yet implemented")
    def test_ascii_period_split_regression(self):
        """I11-3: ASCII 마침표 동작 회귀 없음."""
        text = "First sentence. Second sentence. Third sentence."
        sentences = _split_sentences(text)
        assert len(sentences) == 3, (
            f"ASCII . should still split into 3 sentences, got {len(sentences)}: {sentences}"
        )

    @pytest.mark.skipif(not _HAS_SPLIT, reason="_split_sentences not yet implemented")
    def test_exclamation_and_question_regression(self):
        """I11-4: ! ? 동작 회귀 없음."""
        text = "Really? Yes! Indeed."
        sentences = _split_sentences(text)
        assert len(sentences) == 3, (
            f"! ? . should split into 3 sentences, got {len(sentences)}: {sentences}"
        )

    @pytest.mark.skipif(not _HAS_SPLIT, reason="_split_sentences not yet implemented")
    def test_cjk_exclamation_splits_sentences(self):
        """I11-5: 유니코드 느낌표(！) / 물음표(？)로 분리."""
        text = "정말인가？ 그렇다！ 확실하다。"
        sentences = _split_sentences(text)
        assert len(sentences) == 3, (
            f"！？。 should each split sentences, got {len(sentences)}: {sentences}"
        )

    def test_compress_with_cjk_text_returns_valid_tuple(self):
        """I11-6: 회귀 — CJK 마침표 포함 텍스트도 compress() 정상 반환."""
        result = compress(CJK_PAYLOAD * 3, "Evidence")
        assert isinstance(result, tuple) and len(result) == 3
        assert isinstance(result[0], str)
        assert isinstance(result[1], str) and len(result[1]) == 24
        assert isinstance(result[2], int) and result[2] >= 0
