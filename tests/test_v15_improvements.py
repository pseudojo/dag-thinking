"""
dag-thinking v0.15 improvements — TDD RED phase

I38: _split_sentences 줄임표+공백 false-split 수정 (음성 룩비하인드)
I39: _compress_prose 최소 k=2 (I37 유사 — 산문 과잉 압축 방지)
I40: _action_think depends_on 빈 경우 cycle check 스킵 (동작 동등성 보장)
I41: _action_invalidate target_node 공백 전용 방어
"""

import pytest

from src.compressor import _RATIO_LONG, _RATIO_SHORT, _compress_prose, _split_sentences
from src.server import call_dag_thinking
from tests.helpers import PAYLOAD, invalidate, think

# ---------------------------------------------------------------------------
# I38: _split_sentences 줄임표+공백 false-split 수정
# ---------------------------------------------------------------------------


class TestSplitSentencesEllipsisWithSpace:
    """I38: 줄임표 뒤 공백이 있어도 문장 경계로 오인 분리되지 않아야 함"""

    def test_ellipsis_with_space_not_split(self):
        """I38-T1: 'Wait... really?' (공백 있음) → 1개 (false-split 방지)"""
        result = _split_sentences("Wait... really?")
        assert len(result) == 1, (
            f"줄임표+공백을 문장 경계로 오인 분리: {result}"
        )

    def test_multiple_ellipsis_with_space_not_split(self):
        """I38-T2: 'Go... wait... stop.' (공백 있는 줄임표 연속) → 1개"""
        result = _split_sentences("Go... wait... stop.")
        assert len(result) == 1, (
            f"줄임표 연속 공백 분리 오류: {result}"
        )

    def test_normal_ascii_split_preserved(self):
        """I38-T3: 'Hello. World.' → ['Hello.', 'World.'] (정상 분리 유지)"""
        result = _split_sentences("Hello. World.")
        assert result == ["Hello.", "World."]

    def test_cjk_split_preserved(self):
        """I38-T4: CJK 종결자 즉시 분리 유지"""
        result = _split_sentences("결론이다。다음 단계다。")
        assert len(result) == 2
        assert "결론이다" in result[0]
        assert "다음 단계다" in result[1]

    def test_ellipsis_no_space_still_works(self):
        """I38-T5: 'Wait...really?' (공백 없음) → 여전히 1개"""
        result = _split_sentences("Wait...really?")
        assert len(result) == 1

    def test_empty_string_returns_empty(self):
        """I38-T6: 빈 문자열 → []"""
        assert _split_sentences("") == []


# ---------------------------------------------------------------------------
# I39: _compress_prose 최소 k=2
# ---------------------------------------------------------------------------

def _make_prose(n: int, chars_per_sent: int = 60) -> str:
    """n개 문장으로 구성된 산문 텍스트 생성."""
    sentences = [f"The analysis shows that finding number {i + 1} is important and critical here." for i in range(n)]
    return " ".join(sentences)


class TestCompressProseMinK:
    """I39: _compress_prose — 2문장 이상 산문 최소 2개 보존"""

    def test_two_sentence_prose_ratio_42_keeps_2(self):
        """I39-T1: 2문장, ratio=0.42 → k=max(2,round(0.84))=2 (최소 2개 보존)"""
        text = _make_prose(2)
        result = _compress_prose(text, _RATIO_LONG)
        sentences_out = [s for s in result.split(". ") if s.strip()]
        # 결과가 원문보다 적으면 안 됨 — 최소 2문장 구성 요소 확인
        assert len(result.strip()) > 0
        # 2문장 입력에서 압축 후 원문 대비 최소 절반 이상 유지 (2/2 = 100% 또는 양쪽 보존)
        # 핵심: round(2 * 0.42) = round(0.84) = 1이므로 기존 코드는 1문장 반환 → 버그
        # 수정 후: floor_k=min(2,2)=2 → k=max(2,1)=2 → 2문장 반환
        # 간접 검증: 두 번째 문장의 핵심 단어(number 2)가 포함되어야 함
        assert "number 1" in result or "number 2" in result, (
            "두 번째 문장이 완전히 제거됨 — 최소 k=2 보존 실패"
        )
        # 결과가 단일 문장이 아닌지 확인 (2문장 유지)
        result_sents = _split_sentences(result)
        assert len(result_sents) >= 2, (
            f"2문장 입력이 {len(result_sents)}개 문장으로 과잉 압축됨 (최소 2 필요)"
        )

    def test_three_sentence_prose_ratio_42_keeps_at_least_2(self):
        """I39-T2: 3문장, ratio=0.42 → k=max(2,round(1.26))=max(2,1)=2"""
        text = _make_prose(3)
        result = _compress_prose(text, _RATIO_LONG)
        result_sents = _split_sentences(result)
        assert len(result_sents) >= 2, (
            f"3문장 산문이 {len(result_sents)}개로 과잉 압축됨 (최소 2 필요)"
        )

    def test_one_sentence_prose_keeps_1(self):
        """I39-T3: 1문장 → k=max(min(2,1),...)=1 (변경 없음)"""
        text = "The critical finding shows that the system has a fundamental issue."
        result = _compress_prose(text, _RATIO_LONG)
        result_sents = _split_sentences(result)
        assert len(result_sents) == 1

    def test_five_sentence_prose_ratio_58_keeps_3(self):
        """I39-T4: 5문장, ratio=0.58 → k=max(2,round(2.9))=max(2,3)=3"""
        text = _make_prose(5)
        result = _compress_prose(text, _RATIO_SHORT)
        result_sents = _split_sentences(result)
        assert len(result_sents) == 3, (
            f"5문장 ratio=0.58 결과가 {len(result_sents)}개 (기대: 3)"
        )

    def test_empty_text_returns_empty(self):
        """I39-T5: 빈 텍스트 → 빈 문자열"""
        result = _compress_prose("", _RATIO_LONG)
        assert result == ""


# ---------------------------------------------------------------------------
# I40: depends_on 빈 경우 동작 동등성 (관찰 가능한 동작 변화 없음)
# ---------------------------------------------------------------------------

class TestDependsOnEmptyBehavior:
    """I40: depends_on=[] 시 cycle check 스킵 — 동작 동등성 보장"""

    def test_empty_depends_on_creates_node(self, db_path):
        """I40-T1: depends_on=[] → 정상 생성"""
        result = think(db_path, "s1", "n", "Objective", PAYLOAD, depends_on=[])
        assert result["status"] in ("created", "updated")

    def test_empty_depends_on_no_parent_context(self, db_path):
        """I40-T2: depends_on=[] → 응답에 parent_context 없음"""
        result = think(db_path, "s1", "n", "Objective", PAYLOAD, depends_on=[])
        assert "parent_context" not in result

    def test_nonempty_depends_on_has_parent_context(self, db_path):
        """I40-T3: depends_on=['parent'] → 응답에 parent_context 포함"""
        think(db_path, "s1", "parent", "Objective", PAYLOAD)
        result = think(db_path, "s1", "child", "Hypothesis", PAYLOAD,
                       depends_on=["parent"])
        assert "parent_context" in result
        assert "error" not in result["parent_context"]["parent"]

    def test_first_node_no_edges_no_error(self, db_path):
        """I40-T4: 세션 첫 노드 depends_on=[] → 오류 없음 (그래프 로딩 불필요)"""
        result = think(db_path, "brand_new_session", "first", "Objective", PAYLOAD)
        assert result["status"] == "created"


# ---------------------------------------------------------------------------
# I41: _action_invalidate target_node 공백 전용 방어
# ---------------------------------------------------------------------------

class TestInvalidateTargetNodeWhitespace:
    """I41: target_node 공백 전용 → ValueError (node_name 검증과 동일 패턴)"""

    def test_target_node_none_raises(self, db_path):
        """I41-T1: target_node=None → ValueError"""
        with pytest.raises(ValueError, match="target_node"):
            call_dag_thinking(
                db_path=db_path, action="invalidate",
                session_id="s1", target_node=None, reason=""
            )

    def test_target_node_empty_string_raises(self, db_path):
        """I41-T2: target_node='' → ValueError"""
        with pytest.raises(ValueError, match="target_node"):
            call_dag_thinking(
                db_path=db_path, action="invalidate",
                session_id="s1", target_node="", reason=""
            )

    def test_target_node_whitespace_only_raises(self, db_path):
        """I41-T3: target_node='   ' (공백 전용) → ValueError (현재 버그: 통과)"""
        with pytest.raises(ValueError, match="target_node"):
            call_dag_thinking(
                db_path=db_path, action="invalidate",
                session_id="s1", target_node="   ", reason=""
            )

    def test_target_node_tab_newline_raises(self, db_path):
        """I41-T4: target_node='\\t\\n' → ValueError"""
        with pytest.raises(ValueError, match="target_node"):
            call_dag_thinking(
                db_path=db_path, action="invalidate",
                session_id="s1", target_node="\t\n", reason=""
            )

    def test_valid_target_node_invalidates(self, db_path):
        """I41-T5: 존재하는 노드 target_node → 정상 무효화"""
        think(db_path, "s1", "valid_node", "Objective", PAYLOAD)
        result = invalidate(db_path, "s1", "valid_node")
        assert "invalidated" in result
        assert "valid_node" in result["invalidated"]
