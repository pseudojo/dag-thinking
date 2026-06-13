"""call_dag_thinking 디스패처 행위 테스트 — 액션 라우팅, session_id 검증, info 진단.

PLAN.md §3 명세 + §8 체크리스트 C02, C55~C56 커버.
"""

import importlib.metadata
import os

import pytest

from src.actions import call_dag_thinking
from tests.helpers import status


class TestActionRouting:
    def test_unknown_action_lists_valid_actions(self, db_path):
        """C02: 잘못된 action → 유효 액션 enum 안내."""
        with pytest.raises(ValueError) as exc_info:
            call_dag_thinking(db_path=db_path, action="resolve", session_id="s1")
        msg = str(exc_info.value)
        for action in ("think", "status", "invalidate", "restore", "info"):
            assert action in msg


class TestSessionIdValidation:
    @pytest.mark.parametrize("action", ["think", "status", "invalidate", "restore"])
    def test_blank_session_rejected_for_db_actions(self, db_path, action):
        """P3-12: info 제외 전 액션에서 공백 session_id 거부."""
        with pytest.raises(ValueError, match="session_id"):
            call_dag_thinking(db_path=db_path, action=action, session_id="   ")

    def test_session_id_200_ok_201_rejected(self, db_path):
        """I30: session_id 길이 경계."""
        assert status(db_path, "s" * 200)["session_id"] == "s" * 200
        with pytest.raises(ValueError, match="session_id"):
            status(db_path, "s" * 201)


class TestInfoAction:
    def test_info_requires_no_session(self, db_path):
        """C55: session_id 없이 호출 가능, 전체 필드 반환."""
        info = call_dag_thinking(db_path=db_path, action="info", session_id="")
        assert info["server"] == "dag_thinking_mcp"
        assert info["actions"] == ["think", "status", "invalidate", "restore", "info"]
        assert info["status"] == "ready"
        assert isinstance(info["db_path"], str)
        assert info["db_exists"] == os.path.exists(db_path)

    def test_info_version_is_dynamic(self, db_path):
        """C56/§3.2: version이 패키지 메타데이터와 일치 (하드코딩 금지)."""
        info = call_dag_thinking(db_path=db_path, action="info", session_id="")
        assert info["version"] == importlib.metadata.version("dag-thinking")

    def test_info_reports_missing_db(self, tmp_path):
        """경계: DB 파일 미생성 경로 → db_exists=False (degraded 상태에서도 동작)."""
        ghost = str(tmp_path / "nope.db")
        info = call_dag_thinking(db_path=ghost, action="info", session_id="")
        assert info["db_exists"] is False

    def test_td10_version_matches_document_version(self, db_path):
        """TD-10: pyproject.toml 버전이 문서 버전(≥0.35) 이상이어야 함."""
        info = call_dag_thinking(db_path=db_path, action="info", session_id="")
        ver = info["version"]
        assert ver != "unknown", "버전이 importlib.metadata에서 동적으로 읽혀야 함"
        parts = ver.split(".")
        assert (int(parts[0]), int(parts[1])) >= (0, 35), (
            f"pyproject.toml 버전 미달: {ver!r} < '0.35' — TD-10 해소 필요"
        )


class TestThinkResultTyping:
    def test_parent_context_is_only_optional_field(self):
        """CLEAN-4: ThinkResult에서 parent_context만 선택적, 나머지 7개 필드 필수."""
        from src.think import ThinkResult

        assert "status" in ThinkResult.__required_keys__
        assert ThinkResult.__optional_keys__ == frozenset({"parent_context"})
