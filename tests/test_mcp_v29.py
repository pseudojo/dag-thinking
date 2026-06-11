"""
v0.29 Post-review 수정 검증:
S1: compressor.py 버전 마커 # I06:, # I25:, # I44: 제거
S2: compressor.py # --- 구분선 제거
S3: src/think.py 존재 + _action_think 임포트 가능
S4: actions.py LOC < 500
S5: _action_info version == importlib.metadata version
S6: test_mcp_v28.py unused import asyncio 없음
"""

import importlib.metadata


class TestCompressorCleanupV29:
    """S1-S2: compressor.py 회귀 마커 제거."""

    def test_no_version_markers_in_compressor(self):
        """S1: # I06:, # I25:, # I44: 마커가 compressor.py에 없어야 함."""
        with open("src/compressor.py", encoding="utf-8") as f:
            content = f.read()
        for marker in ("# I06:", "# I25:", "# I44:"):
            assert marker not in content, (
                f"Version marker '{marker}' found in compressor.py — regression from v0.27 cleanup"
            )

    def test_no_section_dividers_in_compressor(self):
        """S2: # ------ 구분선이 compressor.py에 없어야 함."""
        with open("src/compressor.py", encoding="utf-8") as f:
            content = f.read()
        assert "# " + "-" * 14 not in content, (
            "Section dividers (# ----...) found in compressor.py — regression from v0.27 cleanup"
        )


class TestThinkModuleV29:
    """S3-S4: think.py 분리 + actions.py LOC 준수."""

    def test_think_module_exists_with_action_think(self):
        """S3: src/think.py 존재하고 _action_think 임포트 가능."""
        from src.think import _action_think  # noqa: F401

    def test_actions_py_loc_under_500(self):
        """S4: actions.py가 500줄 미만이어야 함 (§4.2 LOC)."""
        with open("src/actions.py", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) < 500, (
            f"actions.py is {len(lines)} lines — MCP Best Practices §4.2 requires < 500 LOC"
        )


class TestDynamicVersionV29:
    """S5: _action_info 동적 버전."""

    def test_info_version_matches_package_metadata(self, db_path):
        """S5: action='info' 반환 version이 importlib.metadata와 일치해야 함."""
        from src.server import call_dag_thinking

        result = call_dag_thinking(action="info", session_id="", db_path=db_path)
        pkg_version = importlib.metadata.version("dag-thinking")
        assert result.get("version") == pkg_version, (
            f"info version '{result.get('version')}' != package version '{pkg_version}' — "
            "§3.2 requires non-hardcoded version"
        )


class TestTestFileCleanupV29:
    """S6: 테스트 파일 품질."""

    def test_no_unused_asyncio_import_in_v28_tests(self):
        """S6: test_mcp_v28.py에 미사용 import asyncio가 없어야 함."""
        with open("tests/test_mcp_v28.py", encoding="utf-8") as f:
            content = f.read()
        assert "import asyncio" not in content, (
            "Unused 'import asyncio' found in test_mcp_v28.py"
        )
