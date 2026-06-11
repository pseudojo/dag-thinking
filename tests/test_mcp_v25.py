"""
v0.25 MCP 표준 준수 개선 검증:
H1: dag_thinking 툴 error handling — ValueError 프로토콜 오류 대신 result dict 반환
H2: FastMCP server 명명 규칙 — dag_thinking_mcp
H3: _split_sentences null byte 취약점 수정
H4: _split_sentences 정상 동작 회귀 없음
"""

import asyncio

from src.compressor import _split_sentences
from src.server import dag_thinking, mcp


class TestMcpErrorHandlingV25:
    """H1-H2: MCP 툴 에러 핸들링 및 서버 명명 규칙."""

    def test_think_without_node_name_returns_error_dict(self):
        """H1: action='think' + node_name=None → isError:True dict 반환 (ValueError 미전파)."""
        result = asyncio.run(
            dag_thinking(
                action="think",
                session_id="test_h1_session",
                node_name=None,
                thought_type="Hypothesis",
                payload="x" * 80,
            )
        )
        assert result.get("isError") is True, (
            f"node_name=None이면 isError:True를 반환해야 함, 실제 결과: {result}"
        )
        assert "error" in result, "error 키가 반환 dict에 있어야 함"
        assert "node_name" in result["error"].lower(), (
            f"error 메시지에 'node_name' 언급 필요, 실제: {result['error']}"
        )

    def test_server_name_follows_mcp_convention(self):
        """H2: FastMCP 서버 이름이 Python MCP 명명 규칙 {service}_mcp 패턴 준수."""
        assert mcp.name == "dag_thinking_mcp", (
            f"서버 이름 '{mcp.name}' — 표준 형식 'dag_thinking_mcp' 필요"
        )


class TestSplitSentencesNullByteV25:
    """H3-H4: _split_sentences null byte 취약점 수정 및 회귀 없음."""

    def test_null_byte_not_treated_as_sentence_boundary(self):
        """H3: text 내 null byte가 문장 경계로 오인되지 않아야 함."""
        text = "Hello world.\x00This is a continuation sentence here."
        result = _split_sentences(text)
        assert len(result) == 1, (
            f"null byte는 문장 경계가 아님 — 1개 문장이어야 하는데 {len(result)}개: {result}"
        )

    def test_normal_ascii_sentence_split_regression(self):
        """H4a: 일반 ASCII 문장 분리 회귀 없음."""
        text = "First sentence here. Second sentence there. Third sentence found."
        result = _split_sentences(text)
        assert len(result) == 3, (
            f"3개 문장이어야 하는데 {len(result)}개: {result}"
        )

    def test_cjk_sentence_split_regression(self):
        """H4b: CJK 문장 분리 회귀 없음."""
        text = "이것은 첫 번째 문장입니다。두 번째 문장입니다。세 번째 문장입니다。"
        result = _split_sentences(text)
        assert len(result) == 3, (
            f"CJK 3개 문장이어야 하는데 {len(result)}개: {result}"
        )
