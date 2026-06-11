"""
v0.27 Skeleton Refactor 검증:
S1: FastMCP 서버에 MCP 표준 준수 description 설정 확인
"""


class TestMcpServerDescriptionV27:
    """S1: MCP 표준 — 서버 수준 description 필수 항목."""

    def test_server_has_instructions(self):
        """S1: mcp.instructions 가 비어있지 않아야 함 (MCP 서버 discoverability)."""
        from src.server import mcp

        assert mcp.instructions, "FastMCP 서버에 instructions가 설정되어 있지 않음"
        assert len(mcp.instructions.strip()) > 10, "instructions가 너무 짧음"
