"""
dag-thinking improvement tests (I06–I08)
TDD RED phase — written before implementation.

문서 근거: LLM 프롬프트 엔지니어링 심층 탐구.md
  I06: thought_type별 키워드 가중치 — ContentRouter 유사 압축 특화
  I07: 세션 컨텍스트 압박 경고 — context_pressure (70-80% 사전 예방)
  I08: DAG 수렴 상태 진단 — dag_health in status
"""

import pytest

from src.compressor import _score_sentence, compress
from tests.helpers import think, status, PAYLOAD


# ---------------------------------------------------------------------------
# I06: thought_type-aware keyword scoring
# ---------------------------------------------------------------------------

class TestThoughtTypeAwareCompression:
    """IC16-IC20: thought_type 기반 압축 특화"""

    def test_ic16_score_sentence_accepts_extra_keywords(self):
        """IC16: _score_sentence가 extra_keywords 파라미터를 받음"""
        sentence = "Data shows measured throughput of 500 RPS at observed latency."
        # Should not raise TypeError
        score = _score_sentence(sentence, 2, 7, extra_keywords=frozenset({"data", "measured"}))
        assert isinstance(score, float)

    def test_ic17_evidence_type_boosts_evidence_sentence(self):
        """IC17: Evidence 타입 키워드 → evidence 문장 스코어 향상"""
        from src.compressor import _TYPE_KEYWORDS
        # 이 문장은 IMPORTANCE_KEYWORDS에 없는 단어만 포함
        sentence = "Data shows measured throughput of 500 RPS at observed latency."
        base = _score_sentence(sentence, 2, 7)
        boosted = _score_sentence(sentence, 2, 7, extra_keywords=_TYPE_KEYWORDS["Evidence"])
        assert boosted > base, (
            f"Evidence 타입 키워드가 스코어를 높이지 못함: base={base:.2f}, boosted={boosted:.2f}"
        )

    def test_ic18_synthesis_type_boosts_conclusion_sentence(self):
        """IC18: Synthesis 타입 키워드 → conclusion 문장 스코어 향상"""
        from src.compressor import _TYPE_KEYWORDS
        # "conclude", "reconcile", "integrate" 는 IMPORTANCE_KEYWORDS 외부
        sentence = "We conclude and reconcile all findings to integrate a comprehensive approach."
        base = _score_sentence(sentence, 2, 7)
        boosted = _score_sentence(sentence, 2, 7, extra_keywords=_TYPE_KEYWORDS["Synthesis"])
        assert boosted > base, (
            f"Synthesis 타입 키워드가 스코어를 높이지 못함: base={base:.2f}, boosted={boosted:.2f}"
        )

    def test_ic19_compress_accepts_thought_type_param(self):
        """IC19: compress()가 thought_type 파라미터를 받음"""
        long_text = PAYLOAD * 2  # 충분히 긴 텍스트
        result, hash_, saved = compress(long_text, "Evidence")
        assert isinstance(result, str)
        assert isinstance(hash_, str)
        assert isinstance(saved, int)

    def test_ic20_think_evidence_type_compression_works(self, db_path):
        """IC20: Evidence thought_type으로 think → compression 정상 동작 (회귀 없음)"""
        result = think(db_path, "s1", "ev", "Evidence")
        assert "compression" in result
        assert "tokens_saved" in result["compression"]
        assert "session_total_saved" in result["compression"]


# ---------------------------------------------------------------------------
# I07: context_pressure
# ---------------------------------------------------------------------------

class TestContextPressure:
    """IC21-IC24: think 응답 context_pressure"""

    def test_ic21_think_has_context_pressure(self, db_path):
        """IC21: think 응답에 context_pressure 필드 존재"""
        result = think(db_path, "s1", "n1", "Objective")
        assert "context_pressure" in result, (
            "think 응답에 context_pressure 누락"
        )

    def test_ic22_first_node_pressure_is_low(self, db_path):
        """IC22: 첫 번째 노드 → context_pressure.level == 'low'"""
        result = think(db_path, "s1", "n1", "Objective")
        assert result["context_pressure"]["level"] == "low", (
            f"첫 노드 후 level이 'low'가 아님: {result['context_pressure']['level']}"
        )

    def test_ic23_pressure_increases_with_many_nodes(self, db_path):
        """IC23: _PRESSURE_MEDIUM 이상 노드 → level이 'medium' 또는 'high'"""
        from src.server import _PRESSURE_MEDIUM
        for i in range(_PRESSURE_MEDIUM):
            ttype = "Objective" if i == 0 else "Hypothesis"
            think(db_path, "s1", f"n{i}", ttype)
        # _PRESSURE_MEDIUM + 1번째 노드
        result = think(db_path, "s1", f"n{_PRESSURE_MEDIUM}", "Evidence")
        level = result["context_pressure"]["level"]
        assert level in ("medium", "high"), (
            f"{_PRESSURE_MEDIUM + 1}개 노드 후에도 level이 'low': {level}"
        )

    def test_ic24_context_pressure_has_required_fields(self, db_path):
        """IC24: context_pressure에 level, node_count, hint 필드 존재"""
        result = think(db_path, "s1", "n1", "Objective")
        cp = result["context_pressure"]
        assert "level" in cp, "level 필드 누락"
        assert "node_count" in cp, "node_count 필드 누락"
        assert "hint" in cp, "hint 필드 누락"
        assert cp["node_count"] >= 1, "node_count가 0 이하"


# ---------------------------------------------------------------------------
# I08: dag_health in status
# ---------------------------------------------------------------------------

class TestDagHealth:
    """IC25-IC29: status 응답 dag_health"""

    def test_ic25_status_has_dag_health(self, db_path):
        """IC25: status 응답에 dag_health 필드 존재"""
        think(db_path, "s1", "n1", "Objective")
        result = status(db_path, "s1")
        assert "dag_health" in result, "status 응답에 dag_health 누락"

    def test_ic26_no_synthesis_not_converging(self, db_path):
        """IC26: Synthesis 없는 세션 → is_converging == False"""
        think(db_path, "s1", "n1", "Objective")
        think(db_path, "s1", "n2", "Hypothesis")
        result = status(db_path, "s1")
        assert result["dag_health"]["is_converging"] is False, (
            "Synthesis 없는데 is_converging이 True"
        )

    def test_ic27_synthesis_node_marks_converging(self, db_path):
        """IC27: Synthesis 노드 추가 → is_converging == True"""
        think(db_path, "s1", "n1", "Objective")
        think(db_path, "s1", "syn", "Synthesis")
        result = status(db_path, "s1")
        assert result["dag_health"]["is_converging"] is True, (
            "Synthesis 노드 있는데 is_converging이 False"
        )

    def test_ic28_orphan_nodes_detected(self, db_path):
        """IC28: 연결 없는 2개 노드 → orphan_nodes 포함"""
        think(db_path, "s1", "n1", "Objective")   # depends_on 없음
        think(db_path, "s1", "n2", "Hypothesis")  # depends_on 없음
        result = status(db_path, "s1")
        orphans = result["dag_health"]["orphan_nodes"]
        assert len(orphans) >= 1, (
            f"연결 없는 2개 노드임에도 orphan_nodes가 비어있음: {orphans}"
        )

    def test_ic29_max_depth_chain(self, db_path):
        """IC29: A→B→C 체인 → max_depth == 2"""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        think(db_path, "s1", "c", "Evidence", depends_on=["b"])
        result = status(db_path, "s1")
        depth = result["dag_health"]["max_depth"]
        assert depth == 2, (
            f"A→B→C 체인의 max_depth가 2가 아님: {depth}"
        )
