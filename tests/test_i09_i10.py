"""
RED-phase tests for I09 and I10.

  I09: estimate_tokens CJK-aware — 한글/한자/히라가나/가타카나 × 2 토큰
  I10: _action_restore INVALIDATED 노드 복원 경고
"""

from src.compressor import estimate_tokens
from tests.helpers import invalidate, restore, think

_LONG_PAYLOAD = (
    "The key finding from this analysis is that the current architecture has a critical bottleneck "
    "in the data pipeline. The assumption is that horizontal scaling will resolve the throughput "
    "issue. Evidence from load tests shows that latency doubles beyond 500 concurrent connections. "
    "Therefore, the conclusion is to implement a message queue to decouple producers "
    "from consumers. "
    "This result must be addressed before the next production release to avoid system failure."
)


# ---------------------------------------------------------------------------
# I09: estimate_tokens CJK-aware
# ---------------------------------------------------------------------------


class TestEstimateTokensCJK:
    # T1: 순수 한글 — Hangul Syllables (U+AC00-U+D7A3)
    def test_hangul_syllables_counted_as_two_tokens_each(self):
        """I09-T1: 한글 5자 → 10토큰 (5 × 2).

        현재: max(1, 5 // 4) = 1 → RED.
        """
        result = estimate_tokens("안녕하세요")
        assert result == 10, (
            f"한글 5자는 10토큰이어야 함, 실제: {result} (현재 len//4=1, CJK×2 미적용 — RED)"
        )

    # T2: 순수 한자 — CJK Unified Ideographs (U+4E00-U+9FFF)
    def test_cjk_unified_ideographs_counted_as_two_tokens(self):
        """I09-T2: 한자 5자 → 10토큰.

        현재: max(1, 5 // 4) = 1 → RED.
        """
        result = estimate_tokens("中文字符测")
        assert result == 10, f"한자 5자는 10토큰이어야 함, 실제: {result}"

    # T3: 순수 히라가나 — Hiragana (U+3040-U+309F)
    def test_hiragana_counted_as_two_tokens(self):
        """I09-T3: 히라가나 5자 → 10토큰.

        현재: max(1, 5 // 4) = 1 → RED.
        """
        result = estimate_tokens("あいうえお")
        assert result == 10, f"히라가나 5자는 10토큰이어야 함, 실제: {result}"

    # T4: 순수 ASCII 회귀 — 기존 동작 유지
    def test_ascii_unchanged(self):
        """I09-T4: 순수 ASCII는 기존 len//4 동작 유지 (회귀 없음)."""
        assert estimate_tokens("hello") == 1  # 5//4=1
        assert estimate_tokens("hello world") == 2  # 11//4=2

    # T5: 혼합 한글+ASCII
    def test_mixed_hangul_and_ascii(self):
        """I09-T5: "안녕 hello" → 한글2×2 + " hello"(6자)//4=1 → 5.

        현재: max(1, 8 // 4) = 2 → RED (기대값 5).
        """
        text = "안녕 hello"  # 한글 2자 + 공백 + ASCII 5자 = 총 8자
        result = estimate_tokens(text)
        assert result == 5, f'"안녕 hello" → 한글2×2=4 + 비CJK6//4=1 → 5, 실제: {result}'

    # T6: 빈 문자열 경계 보호
    def test_empty_string_returns_one(self):
        """I09-T6: 빈 문자열 → 1 (max 보호, 기존 동작 동일)."""
        assert estimate_tokens("") == 1

    # T7: CJK가 동일 길이 ASCII보다 토큰 많음
    def test_cjk_tokens_exceed_ascii_for_same_length(self):
        """I09-T7: 동일 5자에서 CJK > ASCII.

        현재: 둘 다 max(1, 5//4)=1로 동일 → RED.
        """
        cjk_tokens = estimate_tokens("안녕하세요")
        ascii_tokens = estimate_tokens("hello")
        assert cjk_tokens > ascii_tokens, (
            f"CJK({cjk_tokens}) > ASCII({ascii_tokens}) 이어야 함 — RED"
        )

    # T8: 가타카나 — Katakana (U+30A0-U+30FF)
    def test_katakana_counted_as_two_tokens(self):
        """I09-T8: 가타카나 5자 → 10토큰.

        현재: max(1, 5 // 4) = 1 → RED.
        """
        result = estimate_tokens("アイウエオ")
        assert result == 10, f"가타카나 5자는 10토큰이어야 함, 실제: {result}"


# ---------------------------------------------------------------------------
# I10: _action_restore INVALIDATED 노드 복원 경고
# ---------------------------------------------------------------------------


class TestRestoreInvalidatedWarning:
    # T9: COMPLETED 노드 복원 — warning 없음 (정상 경로 회귀)
    def test_completed_node_restore_has_no_warning(self, db_path):
        """I10-T9: COMPLETED 노드 복원 → 'warning' 키 없음."""
        r = think(db_path, "s1", "node_a", "Objective", payload=_LONG_PAYLOAD)
        result = restore(db_path, "s1", r["ccr_hash"])
        assert "warning" not in result, (
            f"COMPLETED 노드 복원에 불필요한 warning 포함: {result.get('warning')}"
        )

    # T10: INVALIDATED 노드 복원 — warning 있어야 함
    def test_invalidated_node_restore_has_warning(self, db_path):
        """I10-T10: INVALIDATED 노드 복원 → 'warning' 키 존재.

        현재: warning 키 없음 → RED.
        """
        r = think(db_path, "s1", "node_a", "Objective", payload=_LONG_PAYLOAD)
        h = r["ccr_hash"]
        invalidate(db_path, "s1", "node_a")
        result = restore(db_path, "s1", h)
        assert "warning" in result, "INVALIDATED 노드 복원 시 'warning' 키가 없음 — RED"

    # T11: warning 메시지에 "INVALIDATED" 포함
    def test_invalidated_restore_warning_mentions_invalidated(self, db_path):
        """I10-T11: warning 메시지에 'INVALIDATED' 문자열 포함."""
        r = think(db_path, "s1", "node_a", "Objective", payload=_LONG_PAYLOAD)
        h = r["ccr_hash"]
        invalidate(db_path, "s1", "node_a")
        result = restore(db_path, "s1", h)
        warning = result.get("warning", "")
        assert "INVALIDATED" in warning, f"warning 메시지에 'INVALIDATED' 없음: {warning!r}"

    # T12: INVALIDATED여도 payload 정상 반환 (비파괴성)
    def test_invalidated_node_payload_still_returned(self, db_path):
        """I10-T12: INVALIDATED 노드도 original_payload 정상 반환."""
        r = think(db_path, "s1", "node_a", "Objective", payload=_LONG_PAYLOAD)
        h = r["ccr_hash"]
        invalidate(db_path, "s1", "node_a")
        result = restore(db_path, "s1", h)
        assert result["original_payload"] == _LONG_PAYLOAD, (
            "INVALIDATED 노드 복원 시 original_payload 손실"
        )

    # T13: 목록 경로(ccr_hash=None) 동작 무변화
    def test_list_path_unaffected(self, db_path):
        """I10-T13: restore(ccr_hash=None) 경로는 변경 없음."""
        think(db_path, "s1", "node_a", "Objective", payload=_LONG_PAYLOAD)
        invalidate(db_path, "s1", "node_a")
        result = restore(db_path, "s1")  # ccr_hash=None
        assert "restorable_nodes" in result
        assert "warning" not in result
