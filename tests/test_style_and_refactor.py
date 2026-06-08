"""
RED-phase tests for STYLE-1, QUAL-1, QUAL-2 refactoring.

  STYLE-1: ruff check src/ must exit 0 (currently 11 violations → RED)
  QUAL-1 : _is_list_content / _compress_list l→line rename (behavior guard)
  QUAL-2 : found variable inline refactor (behavior guard via parent_context tests)
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.compressor import _is_list_content, _compress_list
from tests.helpers import think, status

_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")


# ---------------------------------------------------------------------------
# STYLE-1 + QUAL-1 + I001 + E501: ruff check src/ must pass cleanly
# ---------------------------------------------------------------------------

class TestRuffConformance:

    def test_ruff_no_violations(self):
        """STYLE-1/QUAL-1/I001/E501: src/ must have zero ruff E/F/I violations.

        현재 11건 위반 (E741×4, E501×6, I001×1) → exit code 1 (RED).
        수정 완료 후 exit code 0 (GREEN).
        """
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "src/"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=_PROJECT_ROOT,
        )
        output = result.stdout.decode("utf-8", errors="replace")
        assert result.returncode == 0, (
            f"ruff violations found ({result.returncode}):\n{output}"
        )


# ---------------------------------------------------------------------------
# QUAL-1: _is_list_content 동작 회귀 방지 (l → line 리네임 안전망)
# ---------------------------------------------------------------------------

class TestIsListContentBehavior:
    """_is_list_content 변수명 변경 전후 동작이 동일함을 보장."""

    def test_bullet_list_detected(self):
        """불릿(-) 목록 3줄 이상 → True."""
        text = "- first item\n- second item\n- third item"
        assert _is_list_content(text) is True

    def test_asterisk_list_detected(self):
        """불릿(*) 목록 → True."""
        text = "* alpha\n* beta\n* gamma"
        assert _is_list_content(text) is True

    def test_numbered_list_detected(self):
        """번호 목록(1.) → True."""
        text = "1. step one\n2. step two\n3. step three"
        assert _is_list_content(text) is True

    def test_numbered_paren_list_detected(self):
        """번호 목록(1)) → True."""
        text = "1) first\n2) second\n3) third"
        assert _is_list_content(text) is True

    def test_prose_not_detected(self):
        """일반 산문 → False."""
        text = "This is a prose sentence. It has no list markers at all."
        assert _is_list_content(text) is False

    def test_two_lines_not_list(self):
        """목록이라도 2줄 이하 → False (최소 3줄 조건)."""
        text = "- only one\n- only two"
        assert _is_list_content(text) is False

    def test_empty_string_not_list(self):
        """빈 문자열 → False."""
        assert _is_list_content("") is False

    def test_mixed_mostly_list(self):
        """5줄 중 3줄이 목록(60%) → True."""
        text = "- item a\n- item b\n- item c\nnot a list\nnot a list"
        assert _is_list_content(text) is True

    def test_mixed_mostly_prose(self):
        """5줄 중 2줄만 목록(40%) → False."""
        text = "prose line one\nprose line two\nprose line three\n- item\n- item2"
        assert _is_list_content(text) is False


# ---------------------------------------------------------------------------
# QUAL-1: _compress_list 동작 회귀 방지 (l → line 리네임 안전망)
# ---------------------------------------------------------------------------

class TestCompressListBehavior:

    def test_compress_list_returns_string(self):
        """_compress_list가 문자열을 반환함."""
        text = "- alpha detail here\n- beta detail here\n- gamma detail here"
        result = _compress_list(text, 0.67)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_compress_list_respects_ratio(self):
        """target_ratio=0.5 → 약 절반의 라인 유지."""
        lines = [f"- item {i} with some content" for i in range(10)]
        text = "\n".join(lines)
        result = _compress_list(text, 0.5)
        result_lines = [l for l in result.splitlines() if l.strip()]
        assert len(result_lines) == 5  # round(10 * 0.5)

    def test_compress_list_preserves_order(self):
        """선택된 라인이 원본 순서대로 출력됨."""
        text = "- aaa\n- zzz\n- mmm\n- bbb\n- nnn"
        result = _compress_list(text, 1.0)  # ratio=1.0 → 전체 유지
        result_lines = result.splitlines()
        original_lines = text.splitlines()
        assert result_lines == original_lines


# ---------------------------------------------------------------------------
# QUAL-2: found 변수 인라인화 동작 회귀 방지
# ---------------------------------------------------------------------------

class TestFoundVariableRefactor:
    """found 변수 구조 변경 후 parent_context 동작이 동일함을 보장."""

    _PAYLOAD = (
        "The key finding from this analysis shows that the system has critical bottleneck. "
        "The assumption is that horizontal scaling will resolve the throughput limitation. "
        "Evidence from load tests shows that latency doubles beyond 500 connections. "
        "Therefore, the conclusion is to implement a message queue for decoupling. "
        "This result must be addressed before the next production release to avoid failure."
    )

    def test_empty_depends_on_no_found_access(self, db_path):
        """depends_on=[] → found는 빈 dict, parent_context 없음."""
        result = think(db_path, "s1", "obj", "Objective", payload=self._PAYLOAD)
        assert "parent_context" not in result or result.get("parent_context") == {}

    def test_ghost_parent_in_found_gives_error_entry(self, db_path):
        """depends_on=["ghost"] (미존재) → parent_context["ghost"]["error"] 존재."""
        result = think(db_path, "s1", "obj", "Objective",
                       payload=self._PAYLOAD, depends_on=["ghost"])
        assert "parent_context" in result
        assert "error" in result["parent_context"]["ghost"]

    def test_valid_parent_in_found_gives_payload(self, db_path):
        """depends_on=["parent"] (존재) → parent_context["parent"]["payload"] 존재."""
        think(db_path, "s1", "parent", "Objective", payload=self._PAYLOAD)
        result = think(db_path, "s1", "child", "Hypothesis",
                       payload=self._PAYLOAD, depends_on=["parent"])
        assert "parent_context" in result
        assert "payload" in result["parent_context"]["parent"]

    def test_mixed_ghost_and_valid_parents(self, db_path):
        """depends_on=['real', 'ghost'] → real은 payload, ghost는 error."""
        think(db_path, "s1", "real", "Objective", payload=self._PAYLOAD)
        result = think(db_path, "s1", "child", "Hypothesis",
                       payload=self._PAYLOAD, depends_on=["real", "ghost"])
        pc = result["parent_context"]
        assert "payload" in pc["real"]
        assert "error" in pc["ghost"]
