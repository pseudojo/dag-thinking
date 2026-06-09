"""v0.9 TDD 개선 테스트 — RED 단계.

I12: _split_sentences CJK 공백 없는 분리
I13: _is_list_content middle dot (U+00B7) 제거
I17: _validate_think_inputs depends_on 길이 상한
"""

import pytest

from src.compressor import _split_sentences, _is_list_content
from src.server import _validate_think_inputs


# ---------------------------------------------------------------------------
# I12: _split_sentences — CJK 공백 없는 분리
# ---------------------------------------------------------------------------

class TestI12SplitSentencesCJKNoSpace:
    """_split_sentences가 CJK 종결 문자 뒤 공백 없이도 분리해야 한다."""

    def test_cjk_no_space_consecutive(self):
        """CJK 종결자 연속, 공백 없음 → 각 문장 분리."""
        result = _split_sentences("A。B。C。")
        assert len(result) == 3, f"expected 3 sentences, got {len(result)}: {result}"

    def test_ascii_with_space_regression(self):
        """ASCII 종결자 + 공백 → 기존 동작 회귀 없음."""
        result = _split_sentences("A. B. C.")
        assert len(result) == 3, f"expected 3 sentences, got {len(result)}: {result}"

    def test_cjk_mixed_no_space(self):
        """！？。 혼합, 공백 없음 → 3 문장."""
        result = _split_sentences("A！B？C。")
        assert len(result) == 3, f"expected 3 sentences, got {len(result)}: {result}"

    def test_cjk_mixed_ascii_text(self):
        """ASCII+CJK 혼합 — 'Hello world。OK。'."""
        result = _split_sentences("Hello world。OK。")
        assert len(result) == 2, f"expected 2 sentences, got {len(result)}: {result}"

    def test_empty_string(self):
        """빈 문자열 → 빈 리스트."""
        assert _split_sentences("") == []

    def test_cjk_with_space_still_splits(self):
        """CJK 뒤 공백 있어도 분리 (기존 동작 유지)."""
        result = _split_sentences("A。 B。 C。")
        assert len(result) == 3, f"expected 3 sentences, got {len(result)}: {result}"


# ---------------------------------------------------------------------------
# I13: _is_list_content — middle dot (U+00B7) false positive 제거
# ---------------------------------------------------------------------------

class TestI13IsListContentMiddleDot:
    """· (U+00B7)은 목록 bullet로 인정하지 않아야 한다."""

    def test_middle_dot_not_list(self):
        """· (U+00B7) 사용 → False (목록 아님)."""
        text = "· 항목1\n· 항목2\n· 항목3"
        assert _is_list_content(text) is False, "middle dot should not be treated as list bullet"

    def test_bullet_circle_is_list(self):
        """• (U+2022) 사용 → True (정상 bullet)."""
        text = "• 항목1\n• 항목2\n• 항목3"
        assert _is_list_content(text) is True, "• (U+2022) should be a valid list bullet"

    def test_dash_list_regression(self):
        """- 사용 목록 → True (회귀 없음)."""
        text = "- 첫번째 항목\n- 두번째 항목\n- 세번째 항목"
        assert _is_list_content(text) is True

    def test_numbered_list_regression(self):
        """숫자 목록 → True (회귀 없음)."""
        text = "1. 첫번째\n2. 두번째\n3. 세번째"
        assert _is_list_content(text) is True


# ---------------------------------------------------------------------------
# I17: _validate_think_inputs — depends_on 길이 상한
# ---------------------------------------------------------------------------

class TestI17DependsOnLengthValidation:
    """depends_on 길이가 상한(20)을 초과하면 ValueError를 발생시켜야 한다."""

    _VALID_PAYLOAD = "a" * 80  # 최소 길이 충족

    def test_empty_depends_on_passes(self):
        """depends_on=[] → 정상 통과."""
        _validate_think_inputs("node_a", "Objective", self._VALID_PAYLOAD, [])

    def test_depends_on_at_limit_passes(self):
        """depends_on 20개 → 정상 통과 (상한 정확히)."""
        _validate_think_inputs(
            "node_a", "Objective", self._VALID_PAYLOAD,
            [f"parent_{i}" for i in range(20)],
        )

    def test_depends_on_over_limit_raises(self):
        """depends_on 21개 → ValueError 발생."""
        with pytest.raises(ValueError):
            _validate_think_inputs(
                "node_a", "Objective", self._VALID_PAYLOAD,
                [f"parent_{i}" for i in range(21)],
            )

    def test_depends_on_over_limit_message(self):
        """ValueError 메시지에 초과 수(21)와 상한(20) 모두 포함."""
        with pytest.raises(ValueError, match=r"21") as exc_info:
            _validate_think_inputs(
                "node_a", "Objective", self._VALID_PAYLOAD,
                [f"parent_{i}" for i in range(21)],
            )
        assert "20" in str(exc_info.value)
