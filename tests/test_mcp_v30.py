"""
v0.30 TD-5: MCP 표준 에러 응답 — ToolError → protocol-level isError.

E1: 직접 호출 검증 실패 → ToolError raise (일반 dict 반환 금지)
E2: in-memory Client 경유 검증 실패 → CallToolResult.is_error == True
E3: in-memory Client 경유 정상 호출 → is_error == False (회귀 방지)
"""

import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from src.server import dag_thinking, mcp


class TestToolErrorDirectCall:
    def test_e1_invalid_think_raises_tool_error(self):
        """E1: action='think' + node_name=None → ToolError raise.

        v0.29까지는 {"isError": True, "error": ...} 일반 dict를 반환했으나
        MCP 클라이언트는 이를 성공 결과로 인식한다 (표준 위반).
        v0.30부터 ToolError를 raise하여 FastMCP가 protocol-level
        isError=True + content block으로 변환하도록 한다.
        """
        with pytest.raises(ToolError) as exc_info:
            asyncio.run(
                dag_thinking(
                    action="think",
                    session_id="test_v30_e1",
                    node_name=None,
                    thought_type="Hypothesis",
                    payload="x" * 80,
                )
            )
        assert "node_name" in str(exc_info.value).lower(), (
            f"ToolError 메시지에 'node_name' 언급 필요, 실제: {exc_info.value}"
        )


class TestToolErrorProtocolLevel:
    def test_e2_invalid_call_sets_protocol_is_error(self):
        """E2: in-memory Client 경유 잘못된 호출 → CallToolResult.is_error == True."""

        async def scenario():
            async with Client(mcp) as client:
                return await client.call_tool(
                    "dag_thinking",
                    {"action": "status", "session_id": "   "},
                    raise_on_error=False,
                )

        result = asyncio.run(scenario())
        assert result.is_error is True, (
            f"blank session_id면 protocol-level is_error=True 필요, 실제: {result}"
        )
        text = result.content[0].text
        assert "session_id" in text.lower(), (
            f"에러 content에 'session_id' 언급 필요, 실제: {text}"
        )

    def test_e3_valid_info_call_is_not_error(self):
        """E3: in-memory Client 경유 action='info' → is_error == False (회귀 방지)."""

        async def scenario():
            async with Client(mcp) as client:
                return await client.call_tool(
                    "dag_thinking",
                    {"action": "info"},
                    raise_on_error=False,
                )

        result = asyncio.run(scenario())
        assert result.is_error is False, (
            f"정상 info 호출은 is_error=False 필요, 실제: {result.content}"
        )
