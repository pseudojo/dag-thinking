"""v0.17 개선 테스트 — I46·I47·I48"""

import pytest

from src.compressor import _split_sentences
from src.server import _validate_think_inputs, call_dag_thinking

# ── I46: note=None 방어 ─────────────────────────────────────────────────────

VALID_PAYLOAD = "x" * 80


def test_i46_note_none_does_not_raise():
    """note=None 이 TypeError 없이 정상 통과해야 한다."""
    _validate_think_inputs("node", "Objective", VALID_PAYLOAD, None, None)


def test_i46_note_none_normalizes_then_length_passes():
    """note=None 정규화 후 길이 0 → 500자 제한 통과."""
    _validate_think_inputs("node", "Objective", VALID_PAYLOAD, None, None)


def test_i46_note_empty_string_passes():
    """note='' 기본값 통과."""
    _validate_think_inputs("node", "Objective", VALID_PAYLOAD, None, "")


def test_i46_note_exceeds_max_raises():
    """note 501자 → ValueError."""
    with pytest.raises(ValueError, match="note exceeds"):
        _validate_think_inputs("node", "Objective", VALID_PAYLOAD, None, "x" * 501)


def test_i46_note_exactly_500_passes():
    """note 정확히 500자 → 통과."""
    _validate_think_inputs("node", "Objective", VALID_PAYLOAD, None, "x" * 500)


# ── I47: target_node 공백 정규화 ─────────────────────────────────────────────


@pytest.fixture()
def tmp_db_with_node(tmp_path):
    db_path = str(tmp_path / "test.db")
    from src.server import init_db

    init_db(db_path)
    call_dag_thinking(
        db_path=db_path,
        action="think",
        session_id="s1",
        node_name="mynode",
        thought_type="Objective",
        payload="x" * 80,
    )
    return db_path


def test_i47_padded_target_node_invalidates(tmp_db_with_node):
    """공백 포함 target_node → strip 후 노드 찾아서 무효화."""
    result = call_dag_thinking(
        db_path=tmp_db_with_node,
        action="invalidate",
        session_id="s1",
        target_node=" mynode ",
    )
    assert result["invalidated"] == ["mynode"]


def test_i47_whitespace_only_target_node_raises(tmp_db_with_node):
    """공백 전용 target_node → ValueError."""
    with pytest.raises(ValueError):
        call_dag_thinking(
            db_path=tmp_db_with_node,
            action="invalidate",
            session_id="s1",
            target_node="   ",
        )


def test_i47_none_target_node_raises(tmp_db_with_node):
    """None target_node → ValueError."""
    with pytest.raises(ValueError):
        call_dag_thinking(
            db_path=tmp_db_with_node,
            action="invalidate",
            session_id="s1",
            target_node=None,
        )


def test_i47_exact_name_still_works(tmp_db_with_node):
    """기존 동작: 정확한 이름으로 무효화 정상 작동."""
    result = call_dag_thinking(
        db_path=tmp_db_with_node,
        action="invalidate",
        session_id="s1",
        target_node="mynode",
    )
    assert result["invalidated"] == ["mynode"]


# ── I48: _split_sentences 복합 종결자 ────────────────────────────────────────


def test_i48_basic_ascii_split():
    """기본 ASCII 문장 분리 — 기존 동작 유지."""
    assert _split_sentences("Hello. World.") == ["Hello.", "World."]


def test_i48_ellipsis_no_split():
    """줄임표 뒤 공백 → 분리 안 함 — 기존 동작 유지."""
    assert _split_sentences("Wait... really?") == ["Wait... really?"]


def test_i48_question_exclamation_splits():
    """?! 복합 종결자 뒤 공백 → 분리해야 한다."""
    assert _split_sentences("Really?! Yes.") == ["Really?!", "Yes."]


def test_i48_double_exclamation_splits():
    """!! 이중 감탄 뒤 공백 → 분리해야 한다."""
    assert _split_sentences("No!! OK.") == ["No!!", "OK."]


def test_i48_double_question_splits():
    """?? 이중 물음 뒤 공백 → 분리해야 한다."""
    assert _split_sentences("Wait?? OK.") == ["Wait??", "OK."]


def test_i48_cjk_splits():
    """CJK 종결자 즉시 분리 — 기존 동작 유지."""
    result = _split_sentences("완료！다음。")
    assert "완료！" in result
    assert len(result) >= 2
