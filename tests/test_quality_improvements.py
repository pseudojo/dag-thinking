"""
Quality improvement tests — R-2, R-3, R-4
[STATE: RED] — written before implementation.

R-2: init_db DDL 트랜잭션 안전화 (executescript 제거, 새 컬럼 추가)
R-3: 노드별 tokens_original/tokens_saved 저장 + _action_status payload 스캔 제거
R-4: _resolve_parent_context 독립 함수 추출 (SRP)
"""

import contextlib

import pytest

from src.server import _db, init_db
from tests.helpers import PAYLOAD, invalidate, status, think

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_db(tmp_path):
    path = str(tmp_path / "test_quality.db")
    init_db(path)
    return path


# ---------------------------------------------------------------------------
# R-2: init_db DDL 트랜잭션 안전화
# ---------------------------------------------------------------------------


class TestInitDbDDLSafety:
    def test_r2_t1_wal_mode_enabled(self, tmp_path):
        """R2-T1: init_db 후 journal_mode == 'wal'"""
        path = str(tmp_path / "wal_test.db")
        init_db(path)
        with contextlib.closing(_db(path)) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal", f"Expected wal, got {mode!r}"

    def test_r2_t2_nodes_has_tokens_original_column(self, tmp_path):
        """R2-T2: nodes 테이블에 tokens_original 컬럼 존재"""
        path = str(tmp_path / "col_test.db")
        init_db(path)
        with contextlib.closing(_db(path)) as conn:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(nodes)").fetchall()]
        assert "tokens_original" in columns, f"tokens_original 컬럼 미존재. 현재 컬럼: {columns}"

    def test_r2_t3_nodes_has_tokens_saved_column(self, tmp_path):
        """R2-T3: nodes 테이블에 tokens_saved 컬럼 존재"""
        path = str(tmp_path / "col_test2.db")
        init_db(path)
        with contextlib.closing(_db(path)) as conn:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(nodes)").fetchall()]
        assert "tokens_saved" in columns, f"tokens_saved 컬럼 미존재. 현재 컬럼: {columns}"

    def test_r2_t4_init_db_idempotent(self, tmp_path):
        """R2-T4: init_db 두 번 호출 — 예외 없음"""
        path = str(tmp_path / "idem_test.db")
        init_db(path)
        init_db(path)  # 두 번째 호출 — CREATE TABLE IF NOT EXISTS이므로 안전해야 함

    # test_r2_t5_executescript_not_used — inspect.getsource() 사용, 구현 세부사항 테스트.
    # 동작 보장은 R2-T1(WAL 모드), R2-T2/T3(컬럼 존재), R2-T4(멱등성)로 충분히 커버됨.


# ---------------------------------------------------------------------------
# R-3: 노드별 토큰 저장 + _action_status payload 스캔 제거
# ---------------------------------------------------------------------------


class TestPerNodeTokenStorage:
    def test_r3_t1_think_stores_tokens_original(self, fresh_db):
        """R3-T1: think() 후 nodes.tokens_original > 0"""
        think(fresh_db, "s1", "n1", "Objective")
        with contextlib.closing(_db(fresh_db)) as conn:
            row = conn.execute(
                "SELECT tokens_original FROM nodes WHERE session_id='s1' AND name='n1'"
            ).fetchone()
        assert row is not None, "노드가 저장되지 않음"
        assert row[0] > 0, f"tokens_original이 0 또는 음수: {row[0]}"

    def test_r3_t2_think_stores_tokens_saved(self, fresh_db):
        """R3-T2: think() 후 nodes.tokens_saved >= 0"""
        think(fresh_db, "s1", "n1", "Objective")
        with contextlib.closing(_db(fresh_db)) as conn:
            row = conn.execute(
                "SELECT tokens_saved FROM nodes WHERE session_id='s1' AND name='n1'"
            ).fetchone()
        assert row is not None
        assert row[0] >= 0, f"tokens_saved가 음수: {row[0]}"

    def test_r3_t3_update_refreshes_tokens_original(self, fresh_db):
        """R3-T3: 같은 노드를 다른 payload로 재생성 → tokens_original 갱신"""
        short_payload = PAYLOAD  # 기본 payload
        # 첫 번째 생성
        think(fresh_db, "s1", "n1", "Objective", payload=short_payload)
        with contextlib.closing(_db(fresh_db)) as conn:
            first = conn.execute(
                "SELECT tokens_original FROM nodes WHERE session_id='s1' AND name='n1'"
            ).fetchone()[0]
        # 두 번째 생성 (업데이트 경로) — payload가 2배이므로 tokens_original도 커야 함
        # PAYLOAD*2는 1500자 이하인지 확인 후 사용
        double = PAYLOAD[:700]  # 700자로 자름 (1500자 이하 보장)
        think(fresh_db, "s1", "n1", "Objective", payload=double)
        with contextlib.closing(_db(fresh_db)) as conn:
            second = conn.execute(
                "SELECT tokens_original FROM nodes WHERE session_id='s1' AND name='n1'"
            ).fetchone()[0]
        assert second != first or double == short_payload, (
            f"tokens_original이 업데이트되지 않음: before={first}, after={second}"
        )

    def test_r3_t4_status_metrics_match_db_sum(self, fresh_db):
        """R3-T4: status().metrics.tokens_original == DB SUM(tokens_original)"""
        think(fresh_db, "s1", "n1", "Objective")
        think(fresh_db, "s1", "n2", "Hypothesis")
        s = status(fresh_db, "s1")
        with contextlib.closing(_db(fresh_db)) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(tokens_original),0) FROM nodes "
                "WHERE session_id='s1' AND status='COMPLETED'"
            ).fetchone()
        db_sum = row[0]
        assert s["metrics"]["tokens_original"] == db_sum, (
            f"status metrics와 DB SUM 불일치: "
            f"metrics={s['metrics']['tokens_original']}, db_sum={db_sum}"
        )

    # test_r3_t5_status_query_excludes_payload_column — inspect.getsource(_action_status) 사용,
    # SQL 쿼리 문자열을 직접 파싱하는 구현 세부사항 테스트.
    # 동작 보장은 R3-T4(metrics == DB SUM)와 R3-T6(tokens_saved 집계)으로 커버됨.

    def test_r3_t6_tokens_saved_metric_regression(self, fresh_db):
        """R3-T6: C22 회귀 — status.metrics.tokens_saved == Σ per-think tokens_saved"""
        r1 = think(fresh_db, "s1", "n1", "Objective")
        r2 = think(fresh_db, "s1", "n2", "Hypothesis")
        s = status(fresh_db, "s1")
        expected = r1["compression"]["tokens_saved"] + r2["compression"]["tokens_saved"]
        assert s["metrics"]["tokens_saved"] == expected, (
            f"tokens_saved 집계 오류: metrics={s['metrics']['tokens_saved']}, expected={expected}"
        )


# ---------------------------------------------------------------------------
# R-4: _resolve_parent_context 독립 함수 추출
# ---------------------------------------------------------------------------


class TestResolveParentContext:
    def test_r4_t1_function_importable(self):
        """R4-T1: _resolve_parent_context가 server 모듈에서 임포트 가능"""
        from src.server import _resolve_parent_context  # noqa: F401

    def test_r4_t2_empty_depends_on_returns_empty_dict(self, fresh_db):
        """R4-T2: depends_on=[] → {}"""
        from src.server import _resolve_parent_context

        with contextlib.closing(_db(fresh_db)) as conn:
            result = _resolve_parent_context(conn, "s1", [])
        assert result == {}, f"빈 depends_on이 {{}}을 반환하지 않음: {result}"

    def test_r4_t3_existing_parent_returns_required_fields(self, fresh_db):
        """R4-T3: 존재하는 부모 → thought_type, ccr_hash, is_compressed, payload 모두 포함"""
        from src.server import _ensure_session, _resolve_parent_context

        think(fresh_db, "s1", "parent_node", "Objective")
        with contextlib.closing(_db(fresh_db)) as conn:
            _ensure_session(conn, "s1")
            result = _resolve_parent_context(conn, "s1", ["parent_node"])
        assert "parent_node" in result
        entry = result["parent_node"]
        for field in ("thought_type", "ccr_hash", "is_compressed", "payload"):
            assert field in entry, f"필수 필드 '{field}' 누락: {entry}"

    def test_r4_t4_missing_parent_returns_error_key(self, fresh_db):
        """R4-T4: 존재하지 않는 부모 → {"error": "Node '...' not found"}"""
        from src.server import _ensure_session, _resolve_parent_context

        with contextlib.closing(_db(fresh_db)) as conn:
            _ensure_session(conn, "s1")
            result = _resolve_parent_context(conn, "s1", ["ghost_node"])
        assert "ghost_node" in result
        assert "error" in result["ghost_node"], f"누락 노드에 error 키 없음: {result['ghost_node']}"
        assert "ghost_node" in result["ghost_node"]["error"]

    def test_r4_t5_invalidated_parent_returns_warning(self, fresh_db):
        """R4-T5: INVALIDATED 부모 → warning + is_invalidated=True"""
        from src.server import _ensure_session, _resolve_parent_context

        think(fresh_db, "s1", "bad_node", "Objective")
        invalidate(fresh_db, "s1", "bad_node")
        with contextlib.closing(_db(fresh_db)) as conn:
            _ensure_session(conn, "s1")
            result = _resolve_parent_context(conn, "s1", ["bad_node"])
        assert "bad_node" in result
        entry = result["bad_node"]
        assert entry.get("is_invalidated") is True, f"is_invalidated 누락 또는 False: {entry}"
        assert "warning" in entry, f"warning 필드 누락: {entry}"

    def test_r4_t6_think_depends_on_regression(self, fresh_db):
        """R4-T6: _resolve_parent_context 추출 후 think() depends_on 회귀 없음"""
        think(fresh_db, "s1", "parent", "Objective")
        result = think(fresh_db, "s1", "child", "Hypothesis", depends_on=["parent"])
        assert "parent_context" in result, "depends_on → parent_context 첨부 실패"
        assert "parent" in result["parent_context"]
        assert "payload" in result["parent_context"]["parent"]
