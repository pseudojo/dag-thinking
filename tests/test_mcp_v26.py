"""
v0.26 MCP 표준 준수 개선 검증:
R1: get_session_resource 함수 등록 및 호출 가능
R2: _get_session_resource_data 가 session_id를 포함한 유효한 JSON 반환
R3: 반환 JSON에 dag, metrics, dag_health 필드 포함
"""

import json


class TestMcpResourceV26:
    """R1-R3: MCP Resource — dag-thinking-session://{session_id} 검증."""

    def test_session_resource_function_is_callable(self):
        """R1: get_session_resource 함수가 임포트 가능하고 호출 가능해야 함."""
        from src.server import get_session_resource

        assert callable(get_session_resource), "get_session_resource 함수가 없거나 호출 불가"

    def test_session_resource_returns_valid_json(self, db_path):
        """R2: _get_session_resource_data 는 session_id를 포함한 유효한 JSON 반환."""
        from src.server import _get_session_resource_data

        result = _get_session_resource_data("test_r2_session", db_path)
        data = json.loads(result)
        assert data.get("session_id") == "test_r2_session", (
            f"session_id 필드 불일치: {data.get('session_id')}"
        )

    def test_session_resource_contains_required_fields(self, db_path):
        """R3: 반환 JSON에 dag, metrics, dag_health 필드 포함."""
        from src.server import _get_session_resource_data

        result = _get_session_resource_data("test_r3_session", db_path)
        data = json.loads(result)
        for field in ("dag", "metrics", "dag_health"):
            assert field in data, f"필수 필드 '{field}' 누락: {list(data.keys())}"
