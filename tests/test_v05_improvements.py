"""
v0.5 품질 개선 테스트 — Q-1 ~ Q-6
[STATE: RED] — 현재 구현에서 대부분 실패, 구현 후 전체 통과 목표
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.helpers import invalidate, status, think

# ---------------------------------------------------------------------------
# Q-1: session_total_saved 정확성 (SEV-3 — old_contribution 공식 버그)
# ---------------------------------------------------------------------------

_PAYLOAD_LONG_A = (
    "Comprehensive analysis reveals critical bottleneck in database layer. "
    "The key finding is N+1 query patterns cause exponential load on production. "
    "Therefore we must implement eager loading as the primary solution now. "
    "The assumption is that ORM fixes suffice without raw SQL rewrites in core. "
    "Conclusion: phased rollout minimizes risk to production stability overall. "
    "Evidence from load tests confirms 3x improvement with query batching strategy applied."
)
_PAYLOAD_LONG_B = (
    "Revised analysis shows message broker is the actual bottleneck in system. "
    "The key finding is vertical scaling is more cost-effective for this workload. "
    "Therefore we must implement connection pooling as the primary solution here. "
    "The assumption is pooling reduces latency by 70 percent at peak load times. "
    "Conclusion: validate in staging environment before production deployment step. "
    "Evidence from benchmark confirms 2x throughput with pool size of 20 connections."
)


class TestSessionTotalSavedAccuracy:
    """QC-1~3: session_total_saved는 SUM(per-node tokens_saved)와 일치해야 한다."""

    def test_qc1_update_session_total_saved_equals_new_node_saved(self, db_path):
        """QC-1: 단일 노드 업데이트 후 session_total_saved == 새 노드 tokens_saved"""
        think(db_path, "s1", "n1", "Objective", payload=_PAYLOAD_LONG_A)
        r2 = think(db_path, "s1", "n1", "Objective", payload=_PAYLOAD_LONG_B)
        expected = r2["compression"]["tokens_saved"]
        actual = r2["compression"]["session_total_saved"]
        assert actual == expected, (
            f"QC-1: session_total_saved={actual}, expected={expected}"
        )

    def test_qc2_multi_node_update_session_total_saved(self, db_path):
        """QC-2: 두 노드 중 하나 업데이트 후 session_total_saved == Σ 최신 per-node saved"""
        r2 = think(db_path, "s1", "n2", "Hypothesis", payload=_PAYLOAD_LONG_A)
        think(db_path, "s1", "n1", "Objective", payload=_PAYLOAD_LONG_A)
        r1b = think(db_path, "s1", "n1", "Objective", payload=_PAYLOAD_LONG_B)
        expected = r1b["compression"]["tokens_saved"] + r2["compression"]["tokens_saved"]
        actual = r1b["compression"]["session_total_saved"]
        assert actual == expected, (
            f"QC-2: session_total_saved={actual}, expected={expected}"
        )

    def test_qc3_same_payload_update_session_total_saved_unchanged(self, db_path):
        """QC-3: 동일 payload 재생성 시 session_total_saved 불변 (delta == 0)"""
        r1 = think(db_path, "s1", "n1", "Objective", payload=_PAYLOAD_LONG_A)
        r2 = think(db_path, "s1", "n1", "Objective", payload=_PAYLOAD_LONG_A)
        assert r1["compression"]["session_total_saved"] == r2["compression"]["session_total_saved"], (
            f"QC-3: changed on same-payload update: "
            f"{r1['compression']['session_total_saved']} → {r2['compression']['session_total_saved']}"
        )


# ---------------------------------------------------------------------------
# Q-2: Batch edge fetch — _load_forward_edges / _has_cycle_graph (SEV-1)
# ---------------------------------------------------------------------------


class TestBatchEdgeFetch:
    """QC-4~9: edge 조회 분리 함수 존재 및 사이클 감지 동작 확인."""

    def test_qc4_load_forward_edges_importable(self):
        """QC-4: _load_forward_edges를 src.server에서 import 가능"""
        from src.server import _load_forward_edges  # noqa: F401

    def test_qc5_has_cycle_graph_importable(self):
        """QC-5: _has_cycle_graph를 src.server에서 import 가능"""
        from src.server import _has_cycle_graph  # noqa: F401

    def test_qc6_load_forward_edges_returns_dict(self, db_path):
        """QC-6: _load_forward_edges가 dict 반환"""
        import sqlite3

        from src.server import _ensure_session, _load_forward_edges, init_db

        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        with conn:
            _ensure_session(conn, "s_edge_test")
        result = _load_forward_edges(conn, "s_edge_test")
        conn.close()
        assert isinstance(result, dict)

    def test_qc7_has_cycle_graph_self_reference(self):
        """QC-7: A→A 자기 참조 → True"""
        from src.server import _has_cycle_graph

        assert _has_cycle_graph({}, "A", "A") is True

    def test_qc8_has_cycle_graph_two_hop_cycle(self):
        """QC-8: graph={A:[B]}, 추가 B→A → True"""
        from src.server import _has_cycle_graph

        graph = {"A": ["B"]}
        assert _has_cycle_graph(graph, "B", "A") is True

    def test_qc9_has_cycle_graph_diamond_allowed(self):
        """QC-9: A→B,C; B,C→D — E 추가는 사이클 아님 → False"""
        from src.server import _has_cycle_graph

        graph = {"A": ["B", "C"], "B": ["D"], "C": ["D"]}
        assert _has_cycle_graph(graph, "A", "E") is False


# ---------------------------------------------------------------------------
# Q-3: _validate_think_inputs 추출 (SEV-4 — SRP)
# ---------------------------------------------------------------------------


class TestValidateThinkInputs:
    """QC-10~15: _validate_think_inputs 독립 함수 존재 및 경계값 동작."""

    def test_qc10_validate_think_inputs_importable(self):
        """QC-10: _validate_think_inputs import 가능"""
        from src.server import _validate_think_inputs  # noqa: F401

    def test_qc11_blank_node_name_raises(self):
        """QC-11: 공백만 있는 node_name → ValueError (node_name 언급)"""
        from src.server import _validate_think_inputs

        with pytest.raises(ValueError, match="node_name"):
            _validate_think_inputs("  ", "Objective", "x" * 80)

    def test_qc12_invalid_thought_type_raises(self):
        """QC-12: 잘못된 thought_type → ValueError (thought_type 언급)"""
        from src.server import _validate_think_inputs

        with pytest.raises(ValueError, match="thought_type"):
            _validate_think_inputs("node", "NotAType", "x" * 80)

    def test_qc13_payload_too_short_raises(self):
        """QC-13: 79자 payload → ValueError"""
        from src.server import _validate_think_inputs

        with pytest.raises(ValueError):
            _validate_think_inputs("node", "Objective", "x" * 79)

    def test_qc14_payload_too_long_raises(self):
        """QC-14: 1501자 payload → ValueError"""
        from src.server import _validate_think_inputs

        with pytest.raises(ValueError):
            _validate_think_inputs("node", "Objective", "x" * 1501)

    def test_qc15_valid_inputs_no_exception(self):
        """QC-15: 정상 입력 → 예외 없음"""
        from src.server import _validate_think_inputs

        _validate_think_inputs("my_node", "Objective", "x" * 80)


# ---------------------------------------------------------------------------
# Q-4: Ruff I001 / import 가드 수정
# ---------------------------------------------------------------------------

_SERVER_SRC = Path("src/server.py").read_text(encoding="utf-8")


class TestRuffClean:
    """QC-16~17: ruff 0-violation, bare 'from compressor import' 제거."""

    def test_qc16_ruff_zero_violations(self):
        """QC-16: ruff check src/ → returncode 0"""
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "src/"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"QC-16: ruff violations:\n{result.stdout}"
        )

    def test_qc17_no_bare_compressor_import(self):
        """QC-17: 'from compressor import' 패턴이 src/server.py에 없음"""
        matches = re.findall(
            r"^\s*from compressor import", _SERVER_SRC, re.MULTILINE
        )
        assert not matches, (
            f"QC-17: bare 'from compressor import' found: {matches}"
        )


# ---------------------------------------------------------------------------
# Q-5: _NEXT_HINTS 직접 접근 (dead fallback 제거)
# ---------------------------------------------------------------------------


class TestNextHintsDirect:
    """QC-18~19: _NEXT_HINTS.get() 제거 및 7개 타입 next_hint 정상 반환."""

    def test_qc18_no_get_fallback_for_next_hints(self):
        """QC-18: server.py에서 _NEXT_HINTS.get( 패턴 없음"""
        matches = re.findall(r"_NEXT_HINTS\.get\(", _SERVER_SRC)
        assert not matches, (
            "QC-18: dead fallback _NEXT_HINTS.get() still present"
        )

    def test_qc19_all_thought_types_return_next_hint(self, db_path):
        """QC-19: 7개 모든 valid thought_type에서 next_hint 필드 존재 (회귀)"""
        from src.server import VALID_THOUGHT_TYPES

        payload = (
            "x" * 40 + " important conclusion therefore key finding must result critical evidence "
            "assumption hypothesis objective synthesis action primary core essential fundamental"
        )
        for tt in VALID_THOUGHT_TYPES:
            result = think(db_path, "s_hints", f"node_{tt}", tt, payload=payload)
            assert "next_hint" in result, f"QC-19: next_hint missing for {tt}"
            assert result["next_hint"], f"QC-19: next_hint empty for {tt}"


# ---------------------------------------------------------------------------
# Q-6: 스테일 주석 제거 (ARCH-1)
# ---------------------------------------------------------------------------


class TestStaleCommentRemoved:
    """QC-20~21: 태스크 트래킹 주석(YELLOW_3, stub)이 server.py에 없음."""

    def test_qc20_no_yellow3_in_server(self):
        """QC-20: 'YELLOW_3' 문자열이 server.py에 없음"""
        assert "YELLOW_3" not in _SERVER_SRC, (
            "QC-20: stale YELLOW_3 comment still present in server.py"
        )

    def test_qc21_no_stub_comment_near_resolve_parent_context(self):
        """QC-21: _resolve_parent_context 정의 근방 10줄 내 'stub' 없음"""
        lines = _SERVER_SRC.splitlines()
        for i, line in enumerate(lines):
            if "def _resolve_parent_context" in line:
                region = lines[max(0, i - 3) : i + 10]
                for rline in region:
                    assert "stub" not in rline.lower(), (
                        f"QC-21: 'stub' comment near _resolve_parent_context: {rline!r}"
                    )
                break
