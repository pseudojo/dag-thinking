"""
v0.7 improvements — RED phase tests.

Covers:
  SEC-1:  _action_restore 에러 경로에서 타 세션 ID 노출 제거
  PERF-1: compress/estimate_tokens DB 트랜잭션 밖으로 이동 (기능 회귀 검증)
  PERF-2: _action_status/_action_restore with conn: 범위 축소 (기능 회귀 검증)
  TYPE-1: _db(), _compute_dag_health() 반환 타입 어노테이션 존재 확인
"""

import inspect
import sqlite3

import pytest

from src.server import _compute_dag_health, _db
from tests.helpers import restore, status, think

PAYLOAD = (
    "The key finding from this analysis is that the authentication module lacks rate limiting. "
    "This is a critical vulnerability that must be addressed immediately as the result of penetration testing. "
    "The assumption is that implementing token bucket algorithm will be sufficient. "
    "Therefore we conclude that a middleware-based solution is the fastest path to remediation. "
    "The error was introduced during the last refactor when the old rate limiter was removed."
)

PAYLOAD_B = (
    "The comprehensive analysis of the distributed system performance reveals multiple critical bottlenecks. "
    "First, the key finding is that network latency between microservices accounts for 40% of total request time. "
    "Second, the assumption that in-memory caching would be sufficient has proven incorrect under load. "
    "Therefore, we must implement a distributed cache layer such as Redis to address this critical issue. "
    "The evidence from load testing shows that without caching, the error rate exceeds 5% at 1000 RPS."
)


# ---------------------------------------------------------------------------
# SEC-1: Session ID information leak prevention
# ---------------------------------------------------------------------------

class TestSecSessionIdLeak:
    """S1-1 ~ S1-3: restore error path must not expose other session IDs."""

    def test_cross_session_hash_error_hides_owner_session(self, db_path):
        """S1-1: 타 세션 hash restore 시도 → ValueError, 타 session_id 미포함."""
        r = think(db_path, "owner_session", "node_a", "Objective", PAYLOAD)
        h = r["ccr_hash"]

        with pytest.raises(ValueError) as exc_info:
            restore(db_path, "attacker_session", h)

        error_msg = str(exc_info.value)
        # 에러는 발생해야 함
        assert len(error_msg) > 0
        # 타 세션 ID("owner_session")가 에러 메시지에 노출되면 안 됨
        assert "owner_session" not in error_msg, (
            f"Error message exposes other session ID: {error_msg!r}"
        )

    def test_nonexistent_hash_error_format(self, db_path):
        """S1-2: 존재하지 않는 hash → ValueError, session_id 포함 but 타 세션 없음."""
        with pytest.raises(ValueError) as exc_info:
            restore(db_path, "s1", "nonexistent_hash_0000000000000000000000")

        error_msg = str(exc_info.value)
        # "not found" 관련 메시지
        assert "not found" in error_msg.lower() or "nonexistent_hash" in error_msg

    def test_same_session_restore_unaffected(self, db_path):
        """S1-3: 정상 restore 동작 영향 없음 — SEC-1 변경 후에도 원본 반환."""
        r = think(db_path, "s1", "node_a", "Objective", PAYLOAD)
        h = r["ccr_hash"]
        result = restore(db_path, "s1", h)
        assert result["original_payload"] == PAYLOAD
        assert result["node_name"] == "node_a"


# ---------------------------------------------------------------------------
# PERF-1/PERF-2 regression: functional equivalence after refactor
# ---------------------------------------------------------------------------

class TestPerfRegressions:
    """P1-1, P2-1, P2-2: PERF 변경 후 기능 동일성 검증."""

    def test_think_produces_correct_result(self, db_path):
        """P1-1: PERF-1 변경 후 think 결과 동일."""
        r = think(db_path, "s1", "node_a", "Objective", PAYLOAD)
        assert r["status"] == "created"
        assert r["node"] == "node_a"
        assert len(r["ccr_hash"]) == 24
        assert "compression" in r
        assert "next_hint" in r
        assert "context_pressure" in r

    def test_status_returns_complete_data(self, db_path):
        """P2-1: PERF-2 변경 후 status 결과 동일."""
        think(db_path, "s1", "node_a", "Objective", PAYLOAD)
        think(db_path, "s1", "node_b", "Hypothesis", PAYLOAD_B, depends_on=["node_a"])
        s = status(db_path, "s1")

        assert "dag" in s
        assert "metrics" in s
        assert "restoration_manifest" in s
        assert "dag_health" in s

        names = [n["name"] for n in s["dag"]["nodes"]]
        assert "node_a" in names
        assert "node_b" in names

        edges = {(e["parent"], e["child"]) for e in s["dag"]["edges"]}
        assert ("node_a", "node_b") in edges

        assert s["metrics"]["tokens_original"] > 0

    def test_restore_list_and_payload(self, db_path):
        """P2-2: PERF-2 변경 후 restore(None) 및 restore(hash) 동일."""
        r = think(db_path, "s1", "node_a", "Objective", PAYLOAD)
        h = r["ccr_hash"]

        # list restore
        list_result = restore(db_path, "s1")
        assert "restorable_nodes" in list_result
        entries = list_result["restorable_nodes"]
        assert any(e["name"] == "node_a" for e in entries)

        # payload restore
        payload_result = restore(db_path, "s1", h)
        assert payload_result["original_payload"] == PAYLOAD


# ---------------------------------------------------------------------------
# TYPE-1: Return type annotation existence
# ---------------------------------------------------------------------------

class TestTypeAnnotations:
    """T1-1, T1-2: 반환 타입 어노테이션 정적 확인."""

    def test_db_has_return_type_annotation(self):
        """T1-1: _db() 함수에 sqlite3.Connection 반환 타입 어노테이션 존재."""
        hints = _db.__annotations__
        assert "return" in hints, "_db() must have a return type annotation"
        assert hints["return"] is sqlite3.Connection, (
            f"_db() return type must be sqlite3.Connection, got {hints['return']}"
        )

    def test_compute_dag_health_has_param_annotations(self):
        """T1-2: _compute_dag_health() 파라미터 타입 어노테이션 존재."""
        sig = inspect.signature(_compute_dag_health)
        params = sig.parameters
        for param_name in ("node_rows", "edge_rows"):
            assert params[param_name].annotation is not inspect.Parameter.empty, (
                f"_compute_dag_health() parameter '{param_name}' must have a type annotation"
            )
