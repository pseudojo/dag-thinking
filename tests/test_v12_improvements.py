"""v0.12 TDD 개선 테스트 — RED 단계.

I25: _is_cjk_char 헬퍼 추출 — estimate_tokens와 _score_sentence CJK 정의 통일
I28: _action_restore LEFT JOIN — 2-query를 1-query로 통합
I29: depends_on 중복 항목 제거 — 순서 보존 dedup
I30: session_id 길이 상한 — _MAX_SESSION_ID_LEN=200
"""

import pytest

from src.compressor import _is_cjk_char, estimate_tokens, _score_sentence


# ---------------------------------------------------------------------------
# I25: _is_cjk_char 헬퍼 — CJK 정의 통일
# ---------------------------------------------------------------------------

class TestI25IsCjkChar:
    """_is_cjk_char이 estimate_tokens와 동일한 7개 범위를 커버한다."""

    def test_cjk_extension_a(self):
        """U+3400 (CJK Extension A 시작) → True."""
        assert _is_cjk_char('㐀') is True

    def test_cjk_extension_a_end(self):
        """U+4DBF (CJK Extension A 끝) → True."""
        assert _is_cjk_char('䶿') is True

    def test_cjk_unified(self):
        """U+4E00 (CJK Unified 시작) → True."""
        assert _is_cjk_char('一') is True

    def test_cjk_unified_end(self):
        """U+9FFF (CJK Unified 끝) → True."""
        assert _is_cjk_char('鿿') is True

    def test_cjk_compat(self):
        """U+F900 (CJK Compatibility 시작) → True."""
        assert _is_cjk_char('豈') is True

    def test_cjk_compat_end(self):
        """U+FAFF (CJK Compatibility 끝) → True."""
        assert _is_cjk_char('﫿') is True

    def test_hangul(self):
        """U+AC00 (Hangul Syllables 시작 '가') → True."""
        assert _is_cjk_char('가') is True

    def test_hangul_end(self):
        """U+D7A3 (Hangul Syllables 끝 '힣') → True."""
        assert _is_cjk_char('힣') is True

    def test_hiragana(self):
        """U+3040 (Hiragana 시작) → True."""
        assert _is_cjk_char('぀') is True

    def test_katakana(self):
        """U+30A0 (Katakana 시작) → True."""
        assert _is_cjk_char('゠') is True

    def test_smp_extension_b(self):
        """U+20000 (CJK Extension B, SMP) → True."""
        assert _is_cjk_char('\U00020000') is True

    def test_ascii_false(self):
        """ASCII 'A' → False."""
        assert _is_cjk_char('A') is False

    def test_latin_false(self):
        """라틴 확장 'é' (U+00E9) → False."""
        assert _is_cjk_char('é') is False

    def test_pua_false(self):
        """Private Use Area U+F8FF → False."""
        assert _is_cjk_char('') is False

    def test_boundary_below_ext_a(self):
        """U+33FF (Extension A 직전) → False."""
        assert _is_cjk_char('㏿') is False

    def test_boundary_above_compat(self):
        """U+FB00 (Compat 직후) → False."""
        assert _is_cjk_char('ﬀ') is False


class TestI25EstimateTokensUsesHelper:
    """estimate_tokens가 _is_cjk_char과 동일한 결과를 생성한다."""

    def test_extension_a_char_counts_as_cjk(self):
        """Extension A 문자는 2 토큰 (헬퍼 기반)."""
        assert estimate_tokens('㐀') == 2

    def test_hiragana_char_counts_as_cjk(self):
        """히라가나 문자는 2 토큰 (헬퍼 기반)."""
        assert estimate_tokens('぀') == 2

    def test_pua_not_cjk(self):
        """PUA U+F8FF는 1 토큰 (CJK 아님)."""
        assert estimate_tokens('') == 1

    def test_consistency_with_is_cjk_char(self):
        """_is_cjk_char(ch)=True인 문자는 estimate_tokens에서 2 토큰."""
        test_chars = ['㐀', '一', '豈', '가', '぀', '゠', '\U00020000']
        for ch in test_chars:
            assert _is_cjk_char(ch) is True
            assert estimate_tokens(ch) == 2, f"Expected 2 tokens for {repr(ch)}"


class TestI25ScoreSentenceUsesHelper:
    """_score_sentence의 CJK 감지가 _is_cjk_char과 동일한 범위를 사용한다."""

    def test_hiragana_sentence_not_penalized(self):
        """히라가나 15자 문장 — _is_cjk_char 기준 CJK → length penalty 없음.
        이전 구현(ord > 0x2E7F)도 히라가나(U+3040-)를 포함하므로 동작 동일.
        """
        # 히라가나는 U+3040-U+309F, 모두 > 0x2E7F이므로 이전 구현도 처리됨
        # 하지만 일관성 보장이 목적
        hiragana = 'あいうえおかきくけこさしすせそ'  # 15자
        score = _score_sentence(hiragana, position=1, total=3)
        assert score >= 0.0, f"15-char hiragana should not be penalized, got {score}"

    def test_katakana_sentence_not_penalized(self):
        """가타카나 15자 문장 — CJK → length penalty 없음."""
        katakana = 'アイウエオカキクケコサシスセソ'  # 15자
        score = _score_sentence(katakana, position=1, total=3)
        assert score >= 0.0, f"15-char katakana should not be penalized, got {score}"

    def test_cjk_unified_sentence_not_penalized(self):
        """한자 15자 문장 — CJK → length penalty 없음."""
        cjk = '一二三四五六七八九十一二三四五'  # 15자
        score = _score_sentence(cjk, position=1, total=3)
        assert score >= 0.0, f"15-char CJK should not be penalized, got {score}"


# ---------------------------------------------------------------------------
# I28: _action_restore — LEFT JOIN 단일 쿼리
# ---------------------------------------------------------------------------

class TestI28RestoreJoin:
    """_action_restore가 단일 LEFT JOIN 쿼리로 ccr_store와 node status를 함께 조회한다."""

    def _make_db(self, tmp_path):
        from src.server import init_db, call_dag_thinking
        db = str(tmp_path / "test.db")
        init_db(db)
        return db, call_dag_thinking

    _PAYLOAD = (
        "이것은 충분한 길이의 테스트 페이로드다. "
        "핵심 결론과 중요한 증거가 포함되어 있다. "
        "근본 원인은 성능 병목이며 해결책이 필요하다. "
        "따라서 즉각적인 조치를 취해야 한다. "
    ) * 2

    def test_restore_returns_original_payload(self, tmp_path):
        """ccr_hash로 복원 시 원본 payload가 반환된다."""
        db, cdt = self._make_db(tmp_path)
        r = cdt(
            action="think", session_id="s1", node_name="n1",
            thought_type="Objective", payload=self._PAYLOAD, db_path=db,
        )
        ccr_hash = r["ccr_hash"]
        restored = cdt(action="restore", session_id="s1", ccr_hash=ccr_hash, db_path=db)
        assert restored["original_payload"] == self._PAYLOAD

    def test_restore_invalidated_node_shows_warning(self, tmp_path):
        """INVALIDATED 노드의 ccr_hash 복원 시 warning 필드가 포함된다."""
        db, cdt = self._make_db(tmp_path)
        r = cdt(
            action="think", session_id="s1", node_name="n1",
            thought_type="Objective", payload=self._PAYLOAD, db_path=db,
        )
        ccr_hash = r["ccr_hash"]
        cdt(action="invalidate", session_id="s1", target_node="n1", reason="test", db_path=db)
        restored = cdt(action="restore", session_id="s1", ccr_hash=ccr_hash, db_path=db)
        assert "warning" in restored, "INVALIDATED node restore should include 'warning' key"

    def test_restore_active_node_no_warning(self, tmp_path):
        """COMPLETED 노드 복원 시 warning 필드가 없어야 한다."""
        db, cdt = self._make_db(tmp_path)
        r = cdt(
            action="think", session_id="s1", node_name="n1",
            thought_type="Objective", payload=self._PAYLOAD, db_path=db,
        )
        ccr_hash = r["ccr_hash"]
        restored = cdt(action="restore", session_id="s1", ccr_hash=ccr_hash, db_path=db)
        assert "warning" not in restored, "COMPLETED node should not have warning"

    def test_restore_wrong_session_raises(self, tmp_path):
        """다른 session_id로 복원 시도 → ValueError."""
        db, cdt = self._make_db(tmp_path)
        r = cdt(
            action="think", session_id="s1", node_name="n1",
            thought_type="Objective", payload=self._PAYLOAD, db_path=db,
        )
        ccr_hash = r["ccr_hash"]
        with pytest.raises(ValueError):
            cdt(action="restore", session_id="other_session", ccr_hash=ccr_hash, db_path=db)


# ---------------------------------------------------------------------------
# I29: depends_on 중복 항목 제거
# ---------------------------------------------------------------------------

class TestI29DependsOnDedup:
    """call_dag_thinking이 depends_on 중복을 제거하고 정상 처리한다."""

    _PAYLOAD = (
        "이것은 충분한 길이의 테스트 페이로드다. "
        "핵심 결론과 중요한 증거가 포함되어 있다. "
        "근본 원인은 성능 병목이며 해결책이 필요하다. "
        "따라서 즉각적인 조치를 취해야 한다. "
    ) * 2

    def _make_db(self, tmp_path):
        from src.server import init_db, call_dag_thinking
        db = str(tmp_path / "test.db")
        init_db(db)
        return db, call_dag_thinking

    def test_duplicate_depends_on_succeeds(self, tmp_path):
        """depends_on에 중복 항목이 있어도 ValueError 없이 정상 처리된다."""
        db, cdt = self._make_db(tmp_path)
        cdt(
            action="think", session_id="s1", node_name="parent",
            thought_type="Objective", payload=self._PAYLOAD, db_path=db,
        )
        result = cdt(
            action="think", session_id="s1", node_name="child",
            thought_type="Evidence", payload=self._PAYLOAD,
            depends_on=["parent", "parent"],  # 중복
            db_path=db,
        )
        assert result["status"] in ("created", "updated")

    def test_duplicate_depends_on_single_edge(self, tmp_path):
        """depends_on 중복이 있어도 DAG에는 단일 엣지만 생성된다."""
        db, cdt = self._make_db(tmp_path)
        cdt(
            action="think", session_id="s1", node_name="parent",
            thought_type="Objective", payload=self._PAYLOAD, db_path=db,
        )
        cdt(
            action="think", session_id="s1", node_name="child",
            thought_type="Evidence", payload=self._PAYLOAD,
            depends_on=["parent", "parent", "parent"],  # 3중 중복
            db_path=db,
        )
        status = cdt(action="status", session_id="s1", db_path=db)
        parent_child_edges = [
            e for e in status["dag"]["edges"]
            if e["parent"] == "parent" and e["child"] == "child"
        ]
        assert len(parent_child_edges) == 1, (
            f"Expected 1 edge, got {len(parent_child_edges)}"
        )

    def test_duplicate_does_not_exceed_max_depends_on(self, tmp_path):
        """중복 제거 후 depends_on 길이가 _MAX_DEPENDS_ON을 초과하지 않으면 통과."""
        db, cdt = self._make_db(tmp_path)
        # 부모 노드 1개 생성
        cdt(
            action="think", session_id="s1", node_name="parent",
            thought_type="Objective", payload=self._PAYLOAD, db_path=db,
        )
        # 중복 20개 (실제 고유 항목 = 1개) → MAX_DEPENDS_ON(20) 미초과
        result = cdt(
            action="think", session_id="s1", node_name="child",
            thought_type="Evidence", payload=self._PAYLOAD,
            depends_on=["parent"] * 20,
            db_path=db,
        )
        assert result["status"] in ("created", "updated")


# ---------------------------------------------------------------------------
# I30: session_id 길이 상한
# ---------------------------------------------------------------------------

class TestI30SessionIdLength:
    """session_id가 200자 상한을 초과하면 ValueError를 발생시킨다."""

    _PAYLOAD = "a" * 80

    def _make_db(self, tmp_path):
        from src.server import init_db, call_dag_thinking
        db = str(tmp_path / "test.db")
        init_db(db)
        return db, call_dag_thinking

    def test_session_id_at_limit_passes(self, tmp_path):
        """session_id 200자 → 정상 통과 (상한 경계)."""
        db, cdt = self._make_db(tmp_path)
        result = cdt(
            action="think", session_id="a" * 200, node_name="n1",
            thought_type="Objective", payload=self._PAYLOAD * 2, db_path=db,
        )
        assert result["status"] == "created"

    def test_session_id_over_limit_raises(self, tmp_path):
        """session_id 201자 → ValueError 발생."""
        db, cdt = self._make_db(tmp_path)
        with pytest.raises(ValueError):
            cdt(
                action="think", session_id="a" * 201, node_name="n1",
                thought_type="Objective", payload=self._PAYLOAD * 2, db_path=db,
            )

    def test_session_id_over_limit_message(self, tmp_path):
        """에러 메시지에 실제 길이(201)와 상한(200) 포함."""
        db, cdt = self._make_db(tmp_path)
        with pytest.raises(ValueError, match=r"201") as exc_info:
            cdt(
                action="think", session_id="a" * 201, node_name="n1",
                thought_type="Objective", payload=self._PAYLOAD * 2, db_path=db,
            )
        assert "200" in str(exc_info.value)

    def test_blank_session_id_still_raises_first(self, tmp_path):
        """blank session_id는 길이 검증 이전에 blank 검증으로 ValueError."""
        db, cdt = self._make_db(tmp_path)
        with pytest.raises(ValueError, match=r"empty|blank"):
            cdt(
                action="think", session_id="", node_name="n1",
                thought_type="Objective", payload=self._PAYLOAD * 2, db_path=db,
            )

    def test_status_action_also_validates_session_id(self, tmp_path):
        """status action도 session_id 길이 검증을 통과한다."""
        db, cdt = self._make_db(tmp_path)
        with pytest.raises(ValueError):
            cdt(action="status", session_id="a" * 201, db_path=db)
