"""FastMCP 프로토콜 레이어 행위 테스트 — 단일 툴, 스키마, annotations, 에러 표준, Resource.

PLAN.md §8 체크리스트 C01, C54, C57~C62 + mcp-builder 품질 체크리스트(§9.2) 커버.
in-memory Client로 MCP 라이프사이클(연결→발견→호출)을 검증한다.
"""

import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from src.server import _get_session_resource_data, dag_thinking, mcp


async def _get_tool():
    return await mcp.get_tool("dag_thinking")


def _anyof_string(prop: dict) -> dict:
    """Optional 파라미터의 anyOf에서 string 브랜치 추출."""
    return next((s for s in prop.get("anyOf", []) if s.get("type") == "string"), {})


class TestSingleEntryPoint:
    async def test_exactly_one_tool_exposed(self):
        """C01/C54: 노출 툴이 dag_thinking 1개뿐."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        assert [t.name for t in tools] == ["dag_thinking"]

    def test_server_name_convention(self):
        """mcp-builder: 서버명 {service}_mcp."""
        assert mcp.name == "dag_thinking_mcp"

    def test_instructions_use_xml_semantic_tags(self):
        """§2.2: instructions에 XML 시맨틱 태그."""
        assert "<use_case>" in mcp.instructions
        assert "<important_notes>" in mcp.instructions


class TestToolMetadata:
    async def test_annotations(self):
        """C60: ToolAnnotations 4종 + title."""
        ann = (await _get_tool()).to_mcp_tool().annotations
        assert ann.readOnlyHint is False
        assert ann.destructiveHint is True
        assert ann.idempotentHint is False
        assert ann.openWorldHint is False
        assert ann.title

    async def test_docstring_has_usage_examples(self):
        """mcp-builder: 'Use when:' / \"Don't use when:\" 예시."""
        desc = (await _get_tool()).description or ""
        assert "Use when:" in desc
        assert "Don't use when:" in desc
        for action in ("think", "status", "invalidate", "restore", "info"):
            assert action in desc

    async def test_all_params_have_descriptions(self):
        """§2.1: 10개 파라미터 전체에 description."""
        props = (await _get_tool()).to_mcp_tool().inputSchema["properties"]
        expected = {
            "action",
            "session_id",
            "node_name",
            "thought_type",
            "payload",
            "depends_on",
            "note",
            "target_node",
            "reason",
            "ccr_hash",
        }
        assert expected <= set(props)
        for name in expected:
            assert "description" in props[name], f"{name}에 description 없음"

    async def test_schema_constraints(self):
        """§2.1: 길이 제약이 inputSchema에 노출 — 엄격 스키마."""
        props = (await _get_tool()).to_mcp_tool().inputSchema["properties"]
        assert props["session_id"].get("maxLength") == 200
        assert props["session_id"].get("minLength") is None  # info 호환 (v0.29)
        assert props["session_id"].get("default") == ""
        assert props["note"].get("maxLength") == 500
        assert props["reason"].get("maxLength") == 500
        assert _anyof_string(props["node_name"]).get("maxLength") == 200
        assert _anyof_string(props["target_node"]).get("maxLength") == 200
        payload = _anyof_string(props["payload"])
        assert payload.get("minLength") == 80
        assert payload.get("maxLength") == 1500


class TestProtocolErrors:
    async def test_validation_failure_raises_tool_error(self):
        """C58/TD-5: ValueError → ToolError (일반 dict 반환 금지)."""
        with pytest.raises(ToolError, match="node_name"):
            await dag_thinking(
                action="think",
                session_id="proto_err",
                node_name=None,
                thought_type="Hypothesis",
                payload="x" * 80,
            )

    async def test_invalid_call_sets_protocol_is_error(self):
        """C61: in-memory Client 경유 → CallToolResult.is_error=True + content."""
        async with Client(mcp) as client:
            result = await client.call_tool(
                "dag_thinking",
                {"action": "status", "session_id": "   "},
                raise_on_error=False,
            )
        assert result.is_error is True
        assert "session_id" in result.content[0].text.lower()

    async def test_valid_info_call_is_not_error(self):
        """C62: 정상 호출 회귀 방지 — is_error=False + 진단 필드."""
        async with Client(mcp) as client:
            result = await client.call_tool(
                "dag_thinking", {"action": "info"}, raise_on_error=False
            )
        assert result.is_error is False


class TestSessionResource:
    async def test_resource_template_registered(self):
        """C57: dag-thinking-session://{session_id} 템플릿 등록 (Client 경유 발견)."""
        async with Client(mcp) as client:
            templates = await client.list_resource_templates()
        assert "dag-thinking-session://{session_id}" in [t.uriTemplate for t in templates]

    def test_resource_payload_is_session_snapshot(self, db_path):
        """Resource 본문 — session_id/dag/metrics/dag_health 포함 JSON."""
        data = json.loads(_get_session_resource_data("res_session", db_path))
        assert data["session_id"] == "res_session"
        for field in ("dag", "metrics", "dag_health", "restoration_manifest"):
            assert field in data
