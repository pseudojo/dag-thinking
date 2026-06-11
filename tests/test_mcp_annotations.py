"""
MCP 표준 준수 테스트 — tool annotations 검증
FastMCP tool.to_mcp_tool().annotations → ToolAnnotations 객체로 접근.
"""

import asyncio


def _get_dag_tool():
    """dag_thinking FunctionTool 객체를 동기 컨텍스트에서 반환."""
    from src.server import mcp

    async def _fetch():
        return await mcp.get_tool("dag_thinking")

    return asyncio.run(_fetch())


def _get_input_schema() -> dict:
    """dag_thinking 툴의 MCP inputSchema(JSON Schema dict) 반환."""
    tool = _get_dag_tool()
    assert tool is not None, "dag_thinking 툴이 MCP 서버에 등록되어 있지 않음"
    return tool.to_mcp_tool().inputSchema


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


class TestMcpParameterDescriptions:
    """P1-P6: MCP inputSchema 파라미터 description — LLM 가이던스 품질 검증."""

    def test_action_param_has_description(self):
        """P1: action 파라미터에 description 있어야 한다 (LLM이 4개 동작을 구분 가능)."""
        schema = _get_input_schema()
        prop = schema.get("properties", {}).get("action", {})
        assert "description" in prop, (
            "action 파라미터에 description 없음 — Field(description=...) 미설정"
        )

    def test_session_id_param_has_description(self):
        """P2: session_id 파라미터에 description 있어야 한다."""
        schema = _get_input_schema()
        prop = schema.get("properties", {}).get("session_id", {})
        assert "description" in prop, "session_id 파라미터에 description 없음"

    def test_payload_param_has_description(self):
        """P3: payload 파라미터에 description 있어야 한다 (80-1500자 제약 안내)."""
        schema = _get_input_schema()
        prop = schema.get("properties", {}).get("payload", {})
        assert "description" in prop, "payload 파라미터에 description 없음"

    def test_depends_on_param_has_description(self):
        """P4: depends_on 파라미터에 description 있어야 한다."""
        schema = _get_input_schema()
        prop = schema.get("properties", {}).get("depends_on", {})
        assert "description" in prop, "depends_on 파라미터에 description 없음"

    def test_target_node_param_has_description(self):
        """P5: target_node 파라미터에 description 있어야 한다."""
        schema = _get_input_schema()
        prop = schema.get("properties", {}).get("target_node", {})
        assert "description" in prop, "target_node 파라미터에 description 없음"

    def test_ccr_hash_param_has_description(self):
        """P6: ccr_hash 파라미터에 description 있어야 한다."""
        schema = _get_input_schema()
        prop = schema.get("properties", {}).get("ccr_hash", {})
        assert "description" in prop, "ccr_hash 파라미터에 description 없음"


class TestMcpFieldConstraints:
    """C1-C4: MCP inputSchema Field 제약조건 — session_id, note 범위 스키마 노출 검증."""

    def test_session_id_has_max_length_constraint(self):
        """C1: session_id maxLength=200 in inputSchema."""
        schema = _get_input_schema()
        prop = schema.get("properties", {}).get("session_id", {})
        assert prop.get("maxLength") == 200, (
            f"session_id maxLength 없음 (현재: {prop}) — Field(max_length=200) 미설정"
        )

    def test_session_id_has_min_length_constraint(self):
        """C2: session_id minLength=1 in inputSchema."""
        schema = _get_input_schema()
        prop = schema.get("properties", {}).get("session_id", {})
        assert prop.get("minLength") == 1, (
            f"session_id minLength 없음 (현재: {prop}) — Field(min_length=1) 미설정"
        )

    def test_note_has_max_length_constraint(self):
        """C3: note maxLength=500 in inputSchema."""
        schema = _get_input_schema()
        prop = schema.get("properties", {}).get("note", {})
        assert prop.get("maxLength") == 500, (
            f"note maxLength 없음 (현재: {prop}) — Field(max_length=500) 미설정"
        )

    def test_session_id_description_regression(self):
        """C4: Field 제약 추가 후 session_id description 회귀 없음."""
        schema = _get_input_schema()
        prop = schema.get("properties", {}).get("session_id", {})
        assert "description" in prop, "session_id description 누락 — Field 수정 후 회귀"
