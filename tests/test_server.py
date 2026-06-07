"""
dag-thinking integration tests (T21-T27, checks C01-C23)
RED phase: written before implementation.
"""

import pytest
import tempfile
import os
import sys

# Allow importing src as a package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.compressor import compress, ccr_hash, estimate_tokens
from src.server import call_dag_thinking, init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def think(db_path, session_id, node_name, thought_type, payload, depends_on=None, note=""):
    return call_dag_thinking(
        db_path=db_path,
        action="think",
        session_id=session_id,
        node_name=node_name,
        thought_type=thought_type,
        payload=payload,
        depends_on=depends_on or [],
        note=note,
    )


def status(db_path, session_id):
    return call_dag_thinking(
        db_path=db_path,
        action="status",
        session_id=session_id,
    )


def restore(db_path, session_id, ccr_hash_val=None):
    return call_dag_thinking(
        db_path=db_path,
        action="restore",
        session_id=session_id,
        ccr_hash=ccr_hash_val,
    )


def invalidate(db_path, session_id, target_node, reason="test"):
    return call_dag_thinking(
        db_path=db_path,
        action="invalidate",
        session_id=session_id,
        target_node=target_node,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# T21: think → status → restore round-trip
# ---------------------------------------------------------------------------

class TestThinkStatusRestoreRoundtrip:
    LONG_PAYLOAD = (
        "We need to analyze the root cause of the performance degradation observed in production. "
        "The key finding is that database queries are not using the correct index on the user_id column. "
        "Therefore, we must add a composite index covering user_id and created_at to resolve this critical issue. "
        "The assumption is that the table has fewer than 10M rows, which is a safe estimate based on current growth. "
        "This is a result of the migration script that ran last week and dropped the old index accidentally. "
        "The conclusion is to roll out the fix during the next maintenance window to minimize risk."
    )

    def test_think_returns_node_and_hash(self, db_path):
        """C01/T13: think 응답에 status, node, ccr_hash(24자) 포함"""
        result = think(db_path, "s1", "define_problem", "Objective", self.LONG_PAYLOAD)
        assert result["status"] in ("created", "updated")
        assert result["node"] == "define_problem"
        assert "ccr_hash" in result
        assert len(result["ccr_hash"]) == 24

    def test_status_contains_restoration_manifest(self, db_path):
        """C14/C15/T16: status 응답에 restoration_manifest 항상 포함, restore_cmd 포맷 정확"""
        think(db_path, "s1", "define_problem", "Objective", self.LONG_PAYLOAD)
        s = status(db_path, "s1")
        assert "restoration_manifest" in s
        manifest = s["restoration_manifest"]
        assert "nodes" in manifest
        assert len(manifest["nodes"]) >= 1
        # C15: restore_cmd must be callable format
        node_entry = manifest["nodes"][0]
        assert "restore_cmd" in node_entry
        assert "action='restore'" in node_entry["restore_cmd"]
        assert "session_id=" in node_entry["restore_cmd"]
        assert "ccr_hash=" in node_entry["restore_cmd"]

    def test_restore_returns_original_payload_byte_level(self, db_path):
        """C17/T19: restore 후 original_payload가 원본과 byte-level 동일"""
        # C17: byte-level identity after round-trip
        result = think(db_path, "s1", "define_problem", "Objective", self.LONG_PAYLOAD)
        h = result["ccr_hash"]
        r = restore(db_path, "s1", h)
        assert r["original_payload"] == self.LONG_PAYLOAD

    def test_status_manifest_empty_when_no_nodes(self, db_path):
        """C14: 노드 0개 세션에서도 restoration_manifest 포함, nodes=[]"""
        # C14: restoration_manifest always present, even with 0 nodes
        s = status(db_path, "empty_session")
        assert "restoration_manifest" in s
        assert s["restoration_manifest"]["nodes"] == []

    def test_status_dag_contains_node(self, db_path):
        """T15: status().dag.nodes에 생성한 노드 이름 포함"""
        think(db_path, "s1", "define_problem", "Objective", self.LONG_PAYLOAD)
        s = status(db_path, "s1")
        names = [n["name"] for n in s["dag"]["nodes"]]
        assert "define_problem" in names


# ---------------------------------------------------------------------------
# T22: depends_on → parent_context auto-attach
# ---------------------------------------------------------------------------

class TestDependsOnParentContext:
    PAYLOAD_A = (
        "The objective is to reduce API latency below 200ms. "
        "This is a critical requirement from the SLA agreement with enterprise customers. "
        "Key findings show that 80% of slow requests are caused by synchronous database calls in the hot path. "
        "The assumption here is that we can safely move these calls to async without breaking existing contracts. "
        "Therefore the result of this analysis points to async refactoring as the primary lever."
    )
    PAYLOAD_B = (
        "Hypothesis: replacing synchronous DB calls with async alternatives will reduce p99 latency by 60%. "
        "Evidence from the staging environment shows that async queries complete in under 50ms on average. "
        "The risk is that connection pool exhaustion could occur under high concurrency. "
        "We must monitor pool usage carefully and set conservative limits initially. "
        "The conclusion is that this approach is viable and should be tested in a canary deployment first."
    )

    def test_no_depends_on_no_parent_context(self, db_path):
        """C03/T13: depends_on=[] → 응답에 parent_context 없음(또는 빈 dict)"""
        # C03
        result = think(db_path, "s1", "obj_node", "Objective", self.PAYLOAD_A)
        assert result.get("parent_context", {}) == {} or "parent_context" not in result

    def test_depends_on_attaches_parent_context(self, db_path):
        """C04/T14: depends_on 지정 → 응답에 parent_context.{parent}.payload 자동 첨부"""
        # C04
        think(db_path, "s1", "obj_node", "Objective", self.PAYLOAD_A)
        result = think(db_path, "s1", "hyp_node", "Hypothesis", self.PAYLOAD_B, depends_on=["obj_node"])
        assert "parent_context" in result
        assert "obj_node" in result["parent_context"]
        assert "payload" in result["parent_context"]["obj_node"]

    def test_parent_context_payload_is_compressed_or_equal(self, db_path):
        """C05: parent_context의 payload가 원본 이하 길이 (압축 또는 동일)"""
        # C05: compressed payload must be <= original length
        think(db_path, "s1", "obj_node", "Objective", self.PAYLOAD_A)
        result = think(db_path, "s1", "hyp_node", "Hypothesis", self.PAYLOAD_B, depends_on=["obj_node"])
        parent_payload = result["parent_context"]["obj_node"]["payload"]
        assert len(parent_payload) <= len(self.PAYLOAD_A)

    def test_invalidated_parent_triggers_warning(self, db_path):
        """C06: INVALIDATED 부모를 depends_on → parent_context에 경고/is_invalidated 포함"""
        # C06
        think(db_path, "s1", "obj_node", "Objective", self.PAYLOAD_A)
        invalidate(db_path, "s1", "obj_node")
        result = think(db_path, "s1", "hyp_node", "Hypothesis", self.PAYLOAD_B, depends_on=["obj_node"])
        # Should have a warning but still proceed (or include warning in parent_context)
        assert "parent_context" in result
        assert result["parent_context"]["obj_node"].get("warning") or result["parent_context"]["obj_node"].get("is_invalidated")


# ---------------------------------------------------------------------------
# T23: Cycle detection
# ---------------------------------------------------------------------------

class TestCycleDetection:
    PAYLOAD = (
        "This is an analysis of the system architecture. The key finding is that the current design "
        "creates a circular dependency between modules A and B. The conclusion is that we need to "
        "introduce an interface layer to break this cycle. This is a critical architectural decision "
        "that must be resolved before the next release. The result would be a cleaner separation."
    )

    def test_self_cycle_rejected(self, db_path):
        """C09/T04: 자기 참조(A depends_on A) → ValueError, 노드 미생성"""
        # C09: cycle attempt → error, node not created
        think(db_path, "s1", "node_a", "Objective", self.PAYLOAD)
        with pytest.raises(Exception) as exc_info:
            think(db_path, "s1", "node_a", "Critique", self.PAYLOAD, depends_on=["node_a"])
        assert "cycle" in str(exc_info.value).lower() or "error" in str(exc_info.value).lower()

    def test_a_b_a_cycle_rejected(self, db_path):
        """C09/T04: A→B 후 B depends_on A 시도 → 순환 감지 ValueError"""
        think(db_path, "s1", "node_a", "Objective", self.PAYLOAD)
        think(db_path, "s1", "node_b", "Hypothesis", self.PAYLOAD, depends_on=["node_a"])
        with pytest.raises(Exception):
            think(db_path, "s1", "node_a", "Critique", self.PAYLOAD, depends_on=["node_b"])


# ---------------------------------------------------------------------------
# T24: Cascade invalidation
# ---------------------------------------------------------------------------

class TestCascadeInvalidation:
    PAYLOAD = (
        "Performance analysis shows critical bottleneck in the database layer. "
        "The key finding is that N+1 query patterns are causing exponential load. "
        "Therefore we must implement eager loading and query batching as the result. "
        "The assumption is that ORM-level fixes will be sufficient without raw SQL rewrites. "
        "This conclusion is based on profiling data from the last three production incidents."
    )

    def test_cascade_invalidates_descendants(self, db_path):
        """C20/T05: A→B→C 구조에서 A invalidate → B,C 모두 INVALIDATED"""
        # C20: A→B→C, invalidate A → B and C also INVALIDATED
        think(db_path, "s1", "node_a", "Objective", self.PAYLOAD)
        think(db_path, "s1", "node_b", "Hypothesis", self.PAYLOAD, depends_on=["node_a"])
        think(db_path, "s1", "node_c", "Evidence", self.PAYLOAD, depends_on=["node_b"])
        result = invalidate(db_path, "s1", "node_a")
        assert set(result["invalidated"]) == {"node_a", "node_b", "node_c"}

    def test_single_node_invalidation(self, db_path):
        """C19/T17: 단일 노드 invalidate → status INVALIDATED, invalidated 목록에 포함"""
        # C19
        think(db_path, "s1", "solo", "Objective", self.PAYLOAD)
        result = invalidate(db_path, "s1", "solo")
        assert "solo" in result["invalidated"]

    def test_re_create_invalidated_node_restores_completed(self, db_path):
        """C21/T13: INVALIDATED 노드를 동일 이름으로 think() 재생성 → COMPLETED 복귀"""
        # C21: think() on INVALIDATED node → status=COMPLETED
        think(db_path, "s1", "node_a", "Objective", self.PAYLOAD)
        invalidate(db_path, "s1", "node_a")
        think(db_path, "s1", "node_a", "Objective", self.PAYLOAD)
        s = status(db_path, "s1")
        node = next(n for n in s["dag"]["nodes"] if n["name"] == "node_a")
        assert node["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# T25: restore — list and single
# ---------------------------------------------------------------------------

class TestRestore:
    PAYLOAD = (
        "The key finding from our security audit is that the authentication module lacks rate limiting. "
        "This is a critical vulnerability that must be addressed immediately as the result of penetration testing. "
        "The assumption is that implementing token bucket algorithm will be sufficient. "
        "Therefore we conclude that a middleware-based solution is the fastest path to remediation. "
        "The error was introduced during the last refactor when the old rate limiter was removed."
    )

    def test_restore_without_hash_returns_node_list(self, db_path):
        """C16/T18: restore(ccr_hash=None) → 세션 내 모든 노드 hash 목록 반환"""
        # C16
        think(db_path, "s1", "node_a", "Objective", self.PAYLOAD)
        result = restore(db_path, "s1")
        assert "restorable_nodes" in result
        assert len(result["restorable_nodes"]) >= 1
        entry = result["restorable_nodes"][0]
        assert "name" in entry
        assert "ccr_hash" in entry
        assert "restore_cmd" in entry

    def test_restore_with_hash_returns_original(self, db_path):
        """C17/T19: restore(ccr_hash=X) → original_payload 원본, node_name 일치"""
        # C17
        r = think(db_path, "s1", "node_a", "Objective", self.PAYLOAD)
        h = r["ccr_hash"]
        result = restore(db_path, "s1", h)
        assert result["original_payload"] == self.PAYLOAD
        assert result["node_name"] == "node_a"

    def test_restore_cross_session_rejected(self, db_path):
        """C18: 다른 session_id로 restore 시도 → ValueError (세션 scoping 보장)"""
        # C18: different session_id → error
        r = think(db_path, "s1", "node_a", "Objective", self.PAYLOAD)
        h = r["ccr_hash"]
        with pytest.raises(Exception):
            restore(db_path, "other_session", h)


# ---------------------------------------------------------------------------
# T26: Compression passthrough for short payloads
# ---------------------------------------------------------------------------

class TestCompressionPassthrough:
    def test_short_payload_passthrough(self, db_path):
        """C10/T12: 100자 미만 payload → tokens_saved=0, passthrough"""
        # C10: <100 chars → compressed=NULL, tokens_saved=0
        short = "This is a short payload under 280 characters. " * 2  # ~94 chars
        result = think(db_path, "s1", "short_node", "Objective", short)
        assert result["compression"]["tokens_saved"] == 0

    def test_short_payload_stored_as_original(self, db_path):
        """C12: 짧은 payload도 ccr_store에 원본 저장 → restore 시 byte-level 동일"""
        short = "Key finding: the system is working correctly. No errors detected. All tests pass."
        r = think(db_path, "s1", "short_node", "Objective", short)
        restored = restore(db_path, "s1", r["ccr_hash"])
        assert restored["original_payload"] == short


# ---------------------------------------------------------------------------
# T27: Compression metrics accuracy
# ---------------------------------------------------------------------------

class TestMetrics:
    """T27: 압축 메트릭 정확성 검증 (C22, C23)"""
    LONG_PAYLOAD = (
        "The comprehensive analysis of the distributed system performance reveals multiple critical bottlenecks. "
        "First, the key finding is that network latency between microservices accounts for 40% of total request time. "
        "Second, the assumption that in-memory caching would be sufficient has proven incorrect under load. "
        "Therefore, we must implement a distributed cache layer such as Redis to address this critical issue. "
        "The evidence from load testing shows that without caching, the error rate exceeds 5% at 1000 RPS. "
        "The conclusion is that a phased migration approach is the safest path, starting with read-heavy endpoints. "
        "The result of our analysis points to three key areas: caching, connection pooling, and query optimization. "
        "This risk assessment concludes that the proposed changes carry minimal operational risk if rolled out incrementally."
    )

    def test_tokens_saved_accurate_in_status(self, db_path):
        """C22: status().metrics.tokens_saved == Σ(각 노드 tokens_saved) 일치"""
        # C22: status().metrics.tokens_saved == sum of per-node tokens_saved
        r1 = think(db_path, "s1", "n1", "Objective", self.LONG_PAYLOAD)
        r2 = think(db_path, "s1", "n2", "Hypothesis", self.LONG_PAYLOAD)
        s = status(db_path, "s1")
        expected = r1["compression"]["tokens_saved"] + r2["compression"]["tokens_saved"]
        assert s["metrics"]["tokens_saved"] == expected

    def test_compression_ratio_formula(self, db_path):
        """C23: ratio = 1 - tokens_compressed / tokens_original 공식 검증 (오차 <0.01)"""
        # C23: ratio = 1 - tokens_compressed / tokens_original
        think(db_path, "s1", "n1", "Objective", self.LONG_PAYLOAD)
        s = status(db_path, "s1")
        m = s["metrics"]
        if m["tokens_original"] > 0:
            expected_ratio = 1 - m["tokens_compressed"] / m["tokens_original"]
            assert abs(m["ratio"] - expected_ratio) < 0.01


# ---------------------------------------------------------------------------
# Additional edge-case checks (C01, C02, C07, C08, C10, C11, C13)
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_unknown_action_raises(self, db_path):
        """C02/T20: 잘못된 action → 명확한 오류 메시지 ValueError"""
        # C02
        with pytest.raises(Exception) as exc_info:
            call_dag_thinking(db_path=db_path, action="unknown", session_id="s1")
        assert "action" in str(exc_info.value).lower() or "unknown" in str(exc_info.value).lower()

    def test_payload_too_short_raises(self, db_path):
        """C07/T13: payload 80자 미만 → ValueError"""
        # C07: <80 chars
        with pytest.raises(Exception):
            think(db_path, "s1", "n", "Objective", "too short")

    def test_payload_too_long_raises(self, db_path):
        """C08/T13: payload 1500자 초과 → ValueError"""
        # C08: >1500 chars
        with pytest.raises(Exception):
            think(db_path, "s1", "n", "Objective", "x" * 1501)

    def test_ccr_hash_deterministic(self):
        """C13/T06: 동일 입력 → 동일 24자 hex hash (결정론적)"""
        # C13: same content → same hash
        text = "deterministic content for hashing test"
        h1 = ccr_hash(text)
        h2 = ccr_hash(text)
        assert h1 == h2
        assert len(h1) == 24

    def test_long_payload_compression_ratio(self):
        """C11/T12: 700자+ payload → 75% 이하로 압축 (목표 42% 유지율 ±허용치)"""
        # C11: 700+ chars → ~42% retained (±10%)
        long_text = (
            "The comprehensive analysis of the distributed system performance reveals multiple critical bottlenecks. "
            "First, the key finding is that network latency between microservices accounts for 40% of total request time. "
            "Second, the assumption that in-memory caching would be sufficient has proven incorrect under load. "
            "Therefore, we must implement a distributed cache layer such as Redis to address this critical issue. "
            "The evidence from load testing shows that without caching, the error rate exceeds 5% at 1000 RPS. "
            "The conclusion is that a phased migration approach is the safest path, starting with read-heavy endpoints. "
            "The result of our analysis points to three key areas: caching, connection pooling, and query optimization. "
        )
        assert len(long_text) >= 700
        compressed, _, _ = compress(long_text)
        ratio = len(compressed) / len(long_text)
        # 42% ± 20% tolerance (implementation may vary)
        assert ratio <= 0.75, f"Not compressed enough: ratio={ratio:.2f}"
