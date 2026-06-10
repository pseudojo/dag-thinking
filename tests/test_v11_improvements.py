"""v0.11 TDD 개선 테스트 — RED 단계.

I20: session_total_saved SELECT를 with conn: 외부로 이동 (PERF-2 완성)
I23: CJK Compatibility Ideographs 유니코드 이스케이프 적용
I24: _score_sentence CJK-aware word_count — 순수 CJK 문장 패널티 제거
"""

from src.compressor import _score_sentence, estimate_tokens

# ---------------------------------------------------------------------------
# I20: session_total_saved — 트랜잭션 구조 검증 (행동 동일성)
# ---------------------------------------------------------------------------


class TestI20TransactionRefactor:
    """session_total_saved가 트랜잭션 리팩토링 후에도 정확하게 누적된다."""

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

    def test_session_total_equals_node_saved_on_first_think(self, tmp_path):
        """첫 번째 think 후 session_total_saved == 해당 노드의 tokens_saved."""
        db, cdt = self._make_db(tmp_path)
        r = cdt(
            action="think",
            session_id="s1",
            node_name="n1",
            thought_type="Objective",
            payload=self._LONG_PAYLOAD,
            db_path=db,
        )
        assert r["compression"]["session_total_saved"] == r["compression"]["tokens_saved"]

    def test_session_total_accumulates_across_nodes(self, tmp_path):
        """두 번째 think 이후 session_total_saved ≥ 첫 번째 session_total_saved."""
        db, cdt = self._make_db(tmp_path)
        r1 = cdt(
            action="think",
            session_id="s1",
            node_name="n1",
            thought_type="Objective",
            payload=self._LONG_PAYLOAD,
            db_path=db,
        )
        r2 = cdt(
            action="think",
            session_id="s1",
            node_name="n2",
            thought_type="Evidence",
            payload=self._LONG_PAYLOAD,
            db_path=db,
        )
        assert r2["compression"]["session_total_saved"] >= r1["compression"]["session_total_saved"]

    def test_upsert_same_payload_session_total_unchanged(self, tmp_path):
        """동일 노드 동일 payload 재think: session_total_saved 변화 없음 (delta=0)."""
        db, cdt = self._make_db(tmp_path)
        r1 = cdt(
            action="think",
            session_id="s1",
            node_name="n1",
            thought_type="Objective",
            payload=self._LONG_PAYLOAD,
            db_path=db,
        )
        r2 = cdt(
            action="think",
            session_id="s1",
            node_name="n1",
            thought_type="Objective",
            payload=self._LONG_PAYLOAD,
            db_path=db,
        )
        assert r2["compression"]["session_total_saved"] == r1["compression"]["session_total_saved"]

    def test_session_total_matches_status_metrics(self, tmp_path):
        """think 응답의 session_total_saved가 status().metrics.tokens_saved와 일치."""
        db, cdt = self._make_db(tmp_path)
        cdt(
            action="think",
            session_id="s1",
            node_name="n1",
            thought_type="Objective",
            payload=self._LONG_PAYLOAD,
            db_path=db,
        )
        r2 = cdt(
            action="think",
            session_id="s1",
            node_name="n2",
            thought_type="Evidence",
            payload=self._LONG_PAYLOAD,
            db_path=db,
        )
        status = cdt(action="status", session_id="s1", db_path=db)
        assert r2["compression"]["session_total_saved"] == status["metrics"]["tokens_saved"]


# ---------------------------------------------------------------------------
# I23: estimate_tokens — CJK Compatibility 유니코드 이스케이프 검증
# ---------------------------------------------------------------------------


class TestI23UnicodeEscapeCompatibility:
    """CJK Compatibility Ideographs(U+F900–U+FAFF) 범위가 정확하게 2토큰을 반환한다."""

    def test_f900_is_cjk_compat(self):
        """U+F900 (CJK Compatibility 첫 문자) → 2 토큰."""
        assert estimate_tokens("豈") == 2

    def test_faff_is_cjk_compat(self):
        """U+FAFF (CJK Compatibility 마지막 문자) → 2 토큰."""
        assert estimate_tokens("﫿") == 2

    def test_f950_is_cjk_compat(self):
        """U+F950 (CJK Compatibility 중간 문자) → 2 토큰."""
        assert estimate_tokens("縷") == 2

    def test_f8ff_not_cjk_compat(self):
        """U+F8FF (PUA 블록, Compatibility 직전) → 2 토큰이 아닌 1 토큰."""
        # U+F8FF는 Private Use Area — CJK가 아님
        result = estimate_tokens("")
        assert result == 1, f"U+F8FF should not count as CJK, got {result}"

    def test_fb00_not_cjk_compat(self):
        """U+FB00 (Alphabetic Presentation Forms, Compatibility 직후) → 1 토큰."""
        result = estimate_tokens("ﬀ")
        assert result == 1, f"U+FB00 should not count as CJK, got {result}"

    def test_compat_range_boundary_regression(self):
        """U+F900 and U+FAFF boundary chars return 2 tokens (escape form)."""
        assert estimate_tokens("豈") == 2, "U+F900 should be 2 tokens"
        assert estimate_tokens("﫿") == 2, "U+FAFF should be 2 tokens"


# ---------------------------------------------------------------------------
# I24: _score_sentence — CJK-aware word_count
# ---------------------------------------------------------------------------


class TestI24ScoreSentenceCJKAware:
    """순수 CJK 문장에서 word_count가 0으로 처리되어 균일 패널티를 받지 않아야 한다."""

    def test_long_cjk_sentence_no_length_penalty(self):
        """10자 이상 CJK 문장은 길이 팩터 패널티(-0.5)를 받지 않아야 한다.

        position=0, total=1일 때 position bonus=0 (total<=1), score 기본값 0.
        길이 팩터만 적용: 10자 이상이면 +0.5 또는 0, < 5자면 -0.5.
        """
        # 15개 CJK 문자 — word_count가 CJK count=15로 설정되면 10~40 구간 → +0.5
        long_cjk = "가나다라마바사아자차카타파하하"  # 15자
        score = _score_sentence(long_cjk, position=1, total=3)
        # position=1이고 total=3이면 중간 → bonus 없음, length factor +0.5 기대
        assert score >= 0.0, (
            f"15-char CJK sentence should not have negative base score, got {score}"
        )

    def test_short_cjk_sentence_length_penalty(self):
        """3자 CJK 문장은 길이 팩터 패널티(-0.5)를 받아야 한다 (< 5)."""
        short_cjk = "가나다"  # 3자
        score = _score_sentence(short_cjk, position=1, total=3)
        # 중간 위치, 길이 3 < 5 → -0.5
        assert score < 0.0, f"3-char CJK sentence should have negative score, got {score}"

    def test_long_cjk_scores_higher_than_short_cjk(self):
        """15자 CJK 문장이 3자 CJK 문장보다 높은 점수를 받아야 한다."""
        long_cjk = "가나다라마바사아자차카타파하하"  # 15자
        short_cjk = "가나다"  # 3자
        long_score = _score_sentence(long_cjk, position=1, total=3)
        short_score = _score_sentence(short_cjk, position=1, total=3)
        assert long_score > short_score, (
            f"long CJK({long_score}) should beat short CJK({short_score})"
        )

    def test_ascii_sentences_unaffected(self):
        """ASCII 문장의 점수 계산에 변화 없음 (회귀 방지)."""
        ascii_sentence = "The critical result shows the main finding is important."
        score = _score_sentence(ascii_sentence, position=0, total=3)
        # position=0 → +2.0, keyword hits 있음 → 양수
        assert score > 2.0, f"ASCII sentence with keywords should score > 2.0, got {score}"

    def test_mixed_sentence_uses_ascii_words(self):
        """ASCII와 CJK 혼합 문장은 ASCII 'regex word pattern' 결과가 비어있지 않으면 words 사용."""
        mixed = "The result 결과 shows 보여주다 the evidence."
        score = _score_sentence(mixed, position=1, total=3)
        # "result", "shows", "evidence" 는 IMPORTANCE_KEYWORDS에 포함
        # keyword_hits >= 2 → score > 0
        assert score > 0.0, f"mixed sentence with ASCII keywords should score > 0, got {score}"

    def test_cjk_sentence_with_extra_keywords_no_boost(self):
        """순수 CJK 문장에서 extra_keywords(English) 가중치는 0 (CJK에 적용 불가)."""
        from src.compressor import _TYPE_KEYWORDS

        cjk_sentence = "핵심 결론을 도출하고 통합 분석을 수행한다."
        score_no_extra = _score_sentence(cjk_sentence, position=1, total=3)
        score_with_extra = _score_sentence(
            cjk_sentence,
            position=1,
            total=3,
            extra_keywords=_TYPE_KEYWORDS["Synthesis"],
        )
        # 순수 CJK에서는 extra_keywords 가중치가 0이어야 함 (English words만 있음)
        assert score_with_extra == score_no_extra, (
            f"English extra_keywords should not boost pure CJK: "
            f"{score_no_extra} vs {score_with_extra}"
        )
