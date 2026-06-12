"""compressor.py 행위 테스트 — compress / estimate_tokens / ccr_hash 공개 인터페이스.

PLAN.md §4 압축 알고리즘 스펙 + §8 체크리스트 C10~C13 커버.
_split_sentences는 private이지만 실버그 4건(I33/I38/I48/I49)의 회귀 가드로
최소 테스트를 유지한다 (§12.2 유지 예외).
"""

import re

from src.compressor import _split_sentences, ccr_hash, compress, estimate_tokens

# 700자 이상 — 문장별로 구분되는 장문 산문 (키워드 분포 통제)
LONG_PROSE = (
    "The architecture review began with a detailed walkthrough of the data pipeline. "
    "Engineers gathered around the whiteboard to sketch the current message flow topology. "
    "The key finding is that a critical bottleneck exists in the ingestion layer. "
    "Several diagrams were drawn to illustrate how requests travel between the services. "
    "Latency numbers were collected from the staging environment over several days. "
    "Evidence shows that throughput degrades sharply beyond five hundred connections. "
    "Therefore the conclusion is that a message queue must decouple producers from consumers. "
    "The team agreed to revisit the deployment topology during the next planning meeting."
)

# 280~700자 산문
MEDIUM_PROSE = (
    "The first experiment measured baseline latency under normal load conditions today. "
    "The second experiment doubled the connection count to observe degradation patterns. "
    "The critical finding is that latency growth is superlinear beyond the threshold. "
    "Therefore the conclusion is that connection pooling must be introduced immediately."
)


class TestCompressPassthrough:
    def test_under_100_chars_passthrough(self):
        """C10: 100자 미만 → 원문 그대로, tokens_saved=0."""
        text = "Short note about the system."
        compressed, hash_val, saved = compress(text)
        assert compressed == text
        assert saved == 0
        assert re.fullmatch(r"[0-9a-f]{24}", hash_val)

    def test_boundary_99_chars_passthrough(self):
        """경계: 정확히 99자 → passthrough."""
        text = "a" * 99
        compressed, _, saved = compress(text)
        assert compressed == text
        assert saved == 0

    def test_boundary_100_chars_enters_compression(self):
        """경계: 정확히 100자 → 압축 경로 진입 (크래시 없이 tuple 반환)."""
        text = ("First sentence is here today. " * 3)[:100]
        compressed, hash_val, saved = compress(text)
        assert isinstance(compressed, str)
        assert isinstance(saved, int)
        assert len(compressed) <= len(text)

    def test_savings_below_threshold_passthrough(self):
        """절약 <10% → passthrough (2문장 산문은 최소 k=2로 전체 유지)."""
        text = (
            "The system processes incoming requests through a single queue. "
            "Each request is validated before being written to the store."
        )
        compressed, _, saved = compress(text)
        assert compressed == text
        assert saved == 0

    def test_empty_string_passthrough(self):
        """엣지: 빈 문자열 → passthrough, 해시는 정상 생성."""
        compressed, hash_val, saved = compress("")
        assert compressed == ""
        assert saved == 0
        assert re.fullmatch(r"[0-9a-f]{24}", hash_val)


class TestCompressProse:
    def test_long_prose_compresses(self):
        """C11: 700자 이상 산문 → 유의미한 축약 + tokens_saved > 0."""
        compressed, _, saved = compress(LONG_PROSE)
        assert len(compressed) < len(LONG_PROSE)
        assert saved > 0
        assert len(compressed) / len(LONG_PROSE) < 0.65

    def test_medium_prose_compresses(self):
        """280~700자 산문 → 축약 발생."""
        assert 280 <= len(MEDIUM_PROSE) < 700
        compressed, _, saved = compress(MEDIUM_PROSE)
        assert len(compressed) < len(MEDIUM_PROSE)
        assert saved > 0

    def test_important_keywords_retained(self):
        """IMPORTANCE_KEYWORDS 포함 문장이 우선 보존된다."""
        compressed, _, _ = compress(LONG_PROSE)
        assert "key finding" in compressed or "conclusion" in compressed

    def test_deterministic_hash(self):
        """C13: 동일 내용 → 동일 ccr_hash (결정론)."""
        _, h1, _ = compress(LONG_PROSE)
        _, h2, _ = compress(LONG_PROSE)
        assert h1 == h2
        assert h1 == ccr_hash(LONG_PROSE)

    def test_thought_type_keywords_boost_retention(self):
        """C34/I06: thought_type 특화 키워드 문장이 해당 타입 압축에서 보존된다."""
        filler = [
            "The morning session covered the general planning agenda for everyone involved "
            "and outlined the schedule for the remainder of the busy week ahead. ",
            "Participants shared updates about ongoing initiatives across several departments "
            "and described the staffing changes expected over the coming quarter. ",
            "The data shows measured metric values observed during the test runs clearly. ",
            "Lunch was followed by an open discussion about future collaboration ideas "
            "and a short walk around the campus grounds for the visiting guests. ",
            "The afternoon wrapped up with informal conversations among the attendees "
            "about travel plans and the venue options for the next gathering. ",
            "Closing remarks thanked the organizers for hosting such a pleasant event.",
        ]
        text = "".join(filler)
        assert len(text) >= 700
        compressed, _, _ = compress(text, "Evidence")
        assert "measured" in compressed, f"Evidence 키워드 문장이 보존되어야 함: {compressed!r}"

    def test_compress_accepts_all_thought_types(self):
        """compress(text, thought_type)가 7개 타입 전부 (str, str, int) 반환."""
        for ttype in (
            "Objective",
            "Hypothesis",
            "Assumption",
            "Evidence",
            "Critique",
            "Synthesis",
            "Action",
        ):
            compressed, hash_val, saved = compress(LONG_PROSE, ttype)
            assert isinstance(compressed, str)
            assert isinstance(hash_val, str)
            assert isinstance(saved, int)


class TestCompressList:
    LIST_TEXT = "\n".join(
        [
            "- The ingestion service must validate every incoming record first",
            "- A critical error in the parser causes silent data loss downstream",
            "- The retry policy should use exponential backoff with jitter applied",
            "- Monitoring dashboards need alerts for queue depth and consumer lag",
            "- The conclusion is that backpressure handling is the top priority",
            "- Documentation updates can wait until the next maintenance window",
        ]
    )

    def test_list_compression_samples_items(self):
        """목록 압축 — 아이템 서브셋 보존, 최소 2개 유지."""
        compressed, _, saved = compress(self.LIST_TEXT)
        kept = [line for line in compressed.splitlines() if line.strip()]
        assert 2 <= len(kept) < 6
        assert saved > 0

    def test_list_items_remain_intact(self):
        """보존된 아이템은 원문 라인과 동일 (문장 재작성 없음)."""
        compressed, _, _ = compress(self.LIST_TEXT)
        original_lines = set(self.LIST_TEXT.splitlines())
        for line in compressed.splitlines():
            assert line in original_lines


class TestEstimateTokens:
    def test_ascii_quarter_rule(self):
        """ASCII: len//4."""
        assert estimate_tokens("abcdefgh") == 2

    def test_cjk_double_rule(self):
        """CJK(한글): 문자당 2토큰."""
        assert estimate_tokens("안녕하세요") == 10

    def test_mixed_text(self):
        """혼합: CJK×2 + ASCII//4."""
        assert estimate_tokens("안녕 hello!") == 2 * 2 + 7 // 4

    def test_minimum_one_token(self):
        """엣지: 빈 문자열도 최소 1 토큰."""
        assert estimate_tokens("") == 1


class TestSentenceSplitRegressions:
    """실버그 회귀 가드 — I33/I38(줄임표), I48(복합 종결자), I49(약어), I12(CJK), H3(null byte)."""

    def test_ascii_three_sentences(self):
        assert len(_split_sentences("First one here. Second one there. Third one found.")) == 3

    def test_ellipsis_not_split(self):
        """I33/I38: 줄임표는 문장 경계가 아님 (공백 유무 모두)."""
        assert len(_split_sentences("Wait...really? ok")) <= 2
        assert len(_split_sentences("Wait... really")) == 1

    def test_abbreviation_not_split(self):
        """I49: Dr./Mr. 약어 뒤에서 분리되지 않음."""
        assert len(_split_sentences("Dr. Smith arrived early today.")) == 1

    def test_compound_terminators_split(self):
        """I48: ?!/!? 복합 종결자 뒤 공백 → 경계."""
        assert len(_split_sentences("Really wow?! Yes indeed.")) == 2

    def test_cjk_split_without_space(self):
        """I12: CJK 종결자는 공백 없이 즉시 분리."""
        assert len(_split_sentences("첫 문장입니다。두 번째입니다。세 번째입니다。")) == 3

    def test_null_byte_not_boundary(self):
        """H3: null byte는 문장 경계가 아님."""
        assert len(_split_sentences("Hello world.\x00This continues the sentence here.")) == 1
