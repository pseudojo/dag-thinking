"""v0.10 TDD 개선 테스트 — RED 단계.

I21: _join_sentences 추출 + _compress_prose CJK 재결합 공백 제거
I18: estimate_tokens CJK Extension A / Compatibility / SMP 추가
I20: session_total_saved SELECT 트랜잭션 밖 이동 (회귀 확인)
I22: _validate_think_inputs node_name 길이 상한 (200자)
"""

import pytest

from src.compressor import _join_sentences, compress, estimate_tokens
from src.server import _validate_think_inputs

# ---------------------------------------------------------------------------
# I21: _join_sentences — CJK 재결합 공백 제거
# ---------------------------------------------------------------------------


class TestI21JoinSentences:
    """CJK 종결 문장은 공백 없이, ASCII 종결 문장은 공백으로 재결합해야 한다."""

    def test_cjk_sentences_no_space(self):
        """CJK 종결자로 끝나는 문장은 공백 없이 결합."""
        result = _join_sentences(["A。", "B。", "C。"])
        assert result == "A。B。C。", f"expected no spaces, got: {repr(result)}"

    def test_ascii_sentences_with_space(self):
        """ASCII 종결자로 끝나는 문장은 공백으로 구분."""
        result = _join_sentences(["First.", "Second.", "Third."])
        assert result == "First. Second. Third.", f"got: {repr(result)}"

    def test_mixed_cjk_terminator(self):
        """CJK 종결자로 끝나는 혼합 텍스트는 공백 없이."""
        result = _join_sentences(["Hello world。", "OK。"])
        assert result == "Hello world。OK。", f"got: {repr(result)}"

    def test_empty_list(self):
        """빈 리스트 → 빈 문자열."""
        assert _join_sentences([]) == ""

    def test_single_item(self):
        """단일 항목은 그대로 반환."""
        assert _join_sentences(["단일문장。"]) == "단일문장。"

    def test_exclamation_cjk_no_space(self):
        """！ 종결도 공백 없이."""
        result = _join_sentences(["A！", "B！"])
        assert result == "A！B！"

    def test_question_cjk_no_space(self):
        """？ 종결도 공백 없이."""
        result = _join_sentences(["A？", "B？"])
        assert result == "A？B？"


class TestI21CompressProseCJKNoSpace:
    """compress()가 CJK 텍스트를 압축할 때 ASCII 공백을 삽입하지 않아야 한다."""

    def test_cjk_compression_no_ascii_space_inserted(self):
        """CJK 텍스트 압축 결과에 CJK 문자 사이 ASCII 공백이 없어야 한다."""
        # 700자 이상 CJK 텍스트로 압축 강제
        cjk_text = (
            "이것은 중요한 결론이다。"
            "핵심 발견은 다음과 같다。"
            "증거에 따르면 가설이 맞다。"
            "따라서 조치가 필요하다。"
            "주요 위험 요소가 존재한다。"
            "근본 원인을 분석해야 한다。"
            "해결책을 찾는 것이 필수적이다。"
            "문제의 핵심은 여기에 있다。"
        ) * 4  # 충분한 길이 확보

        compressed, _, tokens_saved = compress(cjk_text, "Evidence")

        if tokens_saved > 0:
            # 압축이 발생한 경우: 한글 문자 사이에 ASCII 공백이 없어야 함
            # "다。 이" 패턴 (CJK 종결 후 ASCII 공백) 은 버그
            import re

            bad_pattern = re.compile(r"[。！？] [^\n]")
            assert not bad_pattern.search(compressed), (
                f"CJK terminator followed by ASCII space found in: {repr(compressed[:200])}"
            )


# ---------------------------------------------------------------------------
# I18: estimate_tokens — CJK 확장 범위
# ---------------------------------------------------------------------------


class TestI18EstimateTokensCJKExtended:
    """CJK Extension A, Compatibility Ideographs, SMP Extension B+를 cjk_count에 포함해야 한다."""

    def test_cjk_extension_a_start(self):
        """CJK Extension A 시작 문자 (U+3400) → 2 토큰."""
        ch = "㐀"
        result = estimate_tokens(ch)
        assert result == 2, f"CJK Extension A char should be 2 tokens, got {result}"

    def test_cjk_extension_a_end(self):
        """CJK Extension A 끝 문자 (U+4DBF) → 2 토큰."""
        ch = "䶿"
        result = estimate_tokens(ch)
        assert result == 2, f"CJK Extension A end char should be 2 tokens, got {result}"

    def test_cjk_compatibility_start(self):
        """CJK Compatibility Ideographs 시작 (U+F900) → 2 토큰."""
        ch = "豈"
        result = estimate_tokens(ch)
        assert result == 2, f"CJK Compatibility char should be 2 tokens, got {result}"

    def test_cjk_smp_extension_b(self):
        """CJK Supplementary (U+20000, Extension B) → 2 토큰."""
        ch = chr(0x20000)
        result = estimate_tokens(ch)
        assert result == 2, f"SMP CJK char should be 2 tokens, got {result}"

    def test_hangul_regression(self):
        """기존 Hangul Syllables 동작 회귀 없음."""
        assert estimate_tokens("가") == 2

    def test_cjk_unified_regression(self):
        """기존 CJK Unified Ideographs 동작 회귀 없음."""
        assert estimate_tokens("一") == 2

    def test_ascii_regression(self):
        """ASCII 동작 회귀 없음 — 단일 문자는 min(1, ...) = 1."""
        assert estimate_tokens("A") == 1

    def test_mixed_extension_a_and_ascii(self):
        """Extension A 1자 + ASCII 4자 → 2 + 1 = 3 토큰."""
        text = "㐀" + "ABCD"
        result = estimate_tokens(text)
        assert result == 3, f"expected 3, got {result}"


# ---------------------------------------------------------------------------
# I20: session_total_saved 트랜잭션 외부 이동 (회귀 확인)
# ---------------------------------------------------------------------------


class TestI20SessionTotalSavedRegression:
    """session_total_saved가 다수 노드 think 후에도 정확히 누적되어야 한다."""

    _LONG_PAYLOAD = (
        "이것은 테스트용 긴 페이로드다. 충분한 길이를 갖추어야 한다. "
        "핵심 결론은 여기에 있다. 중요한 증거가 필요하다. "
        "근본 원인은 성능 병목이다. 해결책은 캐시 도입이다. "
        "따라서 즉각적인 조치가 필요하다. 주요 위험 요소를 점검하라. "
    ) * 3

    def _make_db(self, tmp_path):
        from src.server import call_dag_thinking, init_db

        db = str(tmp_path / "test.db")
        init_db(db)
        return db, call_dag_thinking

    def test_first_think_session_total_saved_accurate(self, tmp_path):
        """첫 번째 think: session_total_saved == 해당 노드의 tokens_saved."""
        db, call_dt = self._make_db(tmp_path)
        result = call_dt(
            action="think",
            session_id="s1",
            node_name="n1",
            thought_type="Objective",
            payload=self._LONG_PAYLOAD,
            db_path=db,
        )
        node_saved = result["compression"]["tokens_saved"]
        session_total = result["compression"]["session_total_saved"]
        assert session_total == node_saved, (
            f"First think: session_total_saved({session_total}) != tokens_saved({node_saved})"
        )

    def test_second_think_accumulates_session_total(self, tmp_path):
        """두 번째 think: session_total_saved가 두 노드 합산."""
        db, call_dt = self._make_db(tmp_path)
        r1 = call_dt(
            action="think",
            session_id="s1",
            node_name="n1",
            thought_type="Objective",
            payload=self._LONG_PAYLOAD,
            db_path=db,
        )
        r2 = call_dt(
            action="think",
            session_id="s1",
            node_name="n2",
            thought_type="Evidence",
            payload=self._LONG_PAYLOAD,
            db_path=db,
        )
        s1 = r1["compression"]["session_total_saved"]
        s2 = r2["compression"]["session_total_saved"]
        assert s2 >= s1, f"session_total_saved should grow: {s1} → {s2}"

    def test_upsert_delta_reflected_in_session_total(self, tmp_path):
        """동일 노드 재think: delta만큼 session_total_saved 변경."""
        db, call_dt = self._make_db(tmp_path)
        r1 = call_dt(
            action="think",
            session_id="s1",
            node_name="n1",
            thought_type="Objective",
            payload=self._LONG_PAYLOAD,
            db_path=db,
        )
        # 동일 노드 재think (payload 동일하므로 delta=0 예상)
        r2 = call_dt(
            action="think",
            session_id="s1",
            node_name="n1",
            thought_type="Objective",
            payload=self._LONG_PAYLOAD,
            db_path=db,
        )
        s1 = r1["compression"]["session_total_saved"]
        s2 = r2["compression"]["session_total_saved"]
        assert s2 == s1, f"Re-think same payload: session_total should be same: {s1} vs {s2}"


# ---------------------------------------------------------------------------
# I22: _validate_think_inputs — node_name 길이 상한
# ---------------------------------------------------------------------------


class TestI22NodeNameLengthValidation:
    """node_name이 200자 상한을 초과하면 ValueError를 발생시켜야 한다."""

    _VALID_PAYLOAD = "a" * 80

    def test_node_name_at_limit_passes(self):
        """node_name 200자 → 정상 통과 (상한 경계)."""
        _validate_think_inputs("a" * 200, "Objective", self._VALID_PAYLOAD)

    def test_node_name_over_limit_raises(self):
        """node_name 201자 → ValueError 발생."""
        with pytest.raises(ValueError):
            _validate_think_inputs("a" * 201, "Objective", self._VALID_PAYLOAD)

    def test_node_name_over_limit_message(self):
        """에러 메시지에 실제 길이(201)와 상한(200) 포함."""
        with pytest.raises(ValueError, match=r"201") as exc_info:
            _validate_think_inputs("a" * 201, "Objective", self._VALID_PAYLOAD)
        assert "200" in str(exc_info.value)

    def test_blank_node_name_still_raises_first(self):
        """blank node_name은 길이 검증 이전에 blank 검증으로 ValueError."""
        with pytest.raises(ValueError, match=r"required|blank"):
            _validate_think_inputs("", "Objective", self._VALID_PAYLOAD)
