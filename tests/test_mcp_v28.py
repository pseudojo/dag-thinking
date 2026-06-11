"""
v0.28 MCP Best Practices 준수 검증:
S1-S4: action='info' — §3.2 diagnostic endpoint
S5:    server.py LOC < 500 — §4.2 code quality
S6:    XML semantic tags in instructions — §2.2 description markup
"""

import asyncio


class TestInfoActionV28:
    """S1-S4: §3.2 info diagnostic endpoint."""

    def test_info_returns_server_name(self, db_path):
        """S1: info action은 서버 이름을 반환해야 함."""
        from src.server import call_dag_thinking

        result = call_dag_thinking(
            action="info", session_id="ignored", db_path=db_path
        )
        assert result.get("server") == "dag_thinking_mcp"

    def test_info_lists_available_actions(self, db_path):
        """S2: info action 목록에 info 자신이 포함되어야 함."""
        from src.server import call_dag_thinking

        result = call_dag_thinking(
            action="info", session_id="ignored", db_path=db_path
        )
        assert "actions" in result
        assert "info" in result["actions"]
        assert "think" in result["actions"]

    def test_info_reports_db_path(self, db_path):
        """S3: info는 db_path 필드를 포함해야 함."""
        from src.server import call_dag_thinking

        result = call_dag_thinking(
            action="info", session_id="ignored", db_path=db_path
        )
        assert "db_path" in result

    def test_info_reports_db_exists(self, db_path):
        """S4: db_exists 는 bool 타입이어야 함."""
        from src.server import call_dag_thinking

        result = call_dag_thinking(
            action="info", session_id="ignored", db_path=db_path
        )
        assert "db_exists" in result
        assert isinstance(result["db_exists"], bool)


class TestCodeQualityV28:
    """S5-S6: §4.2 LOC + §2.2 XML tags."""

    def test_server_py_loc_under_500(self):
        """S5: server.py가 500줄 미만이어야 함 (§4.2 LOC 규칙)."""
        with open("src/server.py", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) < 500, (
            f"server.py is {len(lines)} lines — MCP Best Practices §4.2 requires < 500 LOC"
        )

    def test_instructions_has_xml_semantic_tags(self):
        """S6: FastMCP instructions에 XML 의미 태그가 있어야 함 (§2.2)."""
        from src.server import mcp

        assert mcp.instructions is not None
        assert "<use_case>" in mcp.instructions, (
            "MCP Best Practices §2.2 requires XML-like semantic tags in tool description"
        )
