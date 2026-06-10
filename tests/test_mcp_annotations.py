"""
MCP 표준 준수 테스트 — tool annotations 검증
FastMCP tool.to_mcp_tool().annotations → ToolAnnotations 객체로 접근.
"""

import asyncio

import pytest


def _get_dag_tool():
    """dag_thinking FunctionTool 객체를 동기 컨텍스트에서 반환."""
    from src.server import mcp

    async def _fetch():
        return await mcp.get_tool("dag_thinking")

    return asyncio.run(_fetch())


def _get_mcp_tool_annotations():
    """dag_thinking 툴의 MCP ToolAnnotations 객체를 반환."""
    tool = _get_dag_tool()
    assert tool is not None, "dag_thinking 툴이 MCP 서버에 등록되어 있지 않음"
    return tool.to_mcp_tool().annotations


class TestMcpToolAnnotations:
    """MCP 표준 tool annotations 검증 (readOnly / destructive / idempotent / openWorld)."""

    def test_tool_registered_as_dag_thinking(self):
        """T6: 툴이 'dag_thinking' 이름으로 MCP 서버에 등록되어야 한다."""
        tool = _get_dag_tool()
        assert tool is not None, "dag_thinking 툴이 서버에 없음"
        assert tool.name == "dag_thinking"

    def test_annotations_object_exists(self):
        """T1: dag_thinking 툴에 ToolAnnotations 객체가 있어야 한다."""
        annotations = _get_mcp_tool_annotations()
        assert annotations is not None, "annotations가 None — @mcp.tool(annotations=...) 미설정"

    def test_read_only_hint_is_false(self):
        """T2: readOnlyHint=False — think/invalidate가 DB 쓰기 수행."""
        annotations = _get_mcp_tool_annotations()
        assert annotations.readOnlyHint is False, (
            f"readOnlyHint={annotations.readOnlyHint} (예상: False)"
        )

    def test_destructive_hint_is_true(self):
        """T3: destructiveHint=True — invalidate가 cascade 무효화."""
        annotations = _get_mcp_tool_annotations()
        assert annotations.destructiveHint is True, (
            f"destructiveHint={annotations.destructiveHint} (예상: True)"
        )

    def test_idempotent_hint_is_false(self):
        """T4: idempotentHint=False — think 반복 호출 시 상태 변경."""
        annotations = _get_mcp_tool_annotations()
        assert annotations.idempotentHint is False, (
            f"idempotentHint={annotations.idempotentHint} (예상: False)"
        )

    def test_open_world_hint_is_false(self):
        """T5: openWorldHint=False — 로컬 SQLite만 사용, 외부 시스템 없음."""
        annotations = _get_mcp_tool_annotations()
        assert annotations.openWorldHint is False, (
            f"openWorldHint={annotations.openWorldHint} (예상: False)"
        )

    def test_think_response_regression(self, db_path):
        """T7: think 응답에 thought_type 포함 (MCP 변경 후 회귀 방지)."""
        from tests.helpers import think

        result = think(db_path, "s1", "n1", "Objective")
        assert "thought_type" in result, "thought_type 필드가 think 응답에서 사라짐"
        assert result["thought_type"] == "Objective"
