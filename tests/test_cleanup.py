"""session cleanup (TD-12) 행위 테스트 — cleanup_if_needed 공개 함수.

PLAN.md §10.1 스펙 + T-CL01 ~ T-CL07 커버.
"""

import contextlib
from datetime import datetime, timedelta, timezone

import pytest

from src.db import _db, cleanup_if_needed, get_archive_db_path


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _insert_old_session(db_path: str, session_id: str, days_ago: int = 60) -> None:
    """직접 과거 타임스탬프로 세션 삽입 (API를 우회해 age 초과 테스트용)."""
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    with contextlib.closing(_db(db_path)) as conn:
        with conn:
            conn.execute(
                "INSERT INTO sessions (id, created_at) VALUES (?, ?)",
                (session_id, ts),
            )


def _session_exists(db_path: str, session_id: str) -> bool:
    with contextlib.closing(_db(db_path)) as conn:
        row = conn.execute(
            "SELECT id FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# T-CL01: age 초과 세션 삭제 (delete 정책)
# ---------------------------------------------------------------------------


class TestCleanupDeleteAged:
    def test_age_exceeded_session_is_deleted(self, db_path):
        """T-CL01: created_at < cutoff 세션이 delete 정책 하에서 삭제된다."""
        _insert_old_session(db_path, "old_session", days_ago=60)

        n = cleanup_if_needed(
            db_path, "current", max_age_days=30, max_count=0, policy="delete"
        )

        assert n == 1
        assert not _session_exists(db_path, "old_session")

    def test_all_related_rows_deleted(self, db_path):
        """T-CL01 확장: nodes/edges/ccr_store도 함께 삭제된다."""
        _insert_old_session(db_path, "old_session", days_ago=60)
        # 관련 레코드 직접 삽입
        with contextlib.closing(_db(db_path)) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO nodes (session_id, name, thought_type, payload, "
                    "ccr_hash, status, tokens_original, tokens_saved) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ("old_session", "n1", "Objective", "x" * 80, "a" * 24, "COMPLETED", 20, 0),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO ccr_store (hash, session_id, node_name, original) "
                    "VALUES (?, ?, ?, ?)",
                    ("a" * 24, "old_session", "n1", "x" * 80),
                )

        cleanup_if_needed(db_path, "current", max_age_days=30, max_count=0, policy="delete")

        with contextlib.closing(_db(db_path)) as conn:
            assert conn.execute(
                "SELECT count(*) FROM nodes WHERE session_id='old_session'"
            ).fetchone()[0] == 0
            assert conn.execute(
                "SELECT count(*) FROM ccr_store WHERE session_id='old_session'"
            ).fetchone()[0] == 0


# ---------------------------------------------------------------------------
# T-CL02: max_count 초과 시 가장 오래된 세션 삭제
# ---------------------------------------------------------------------------


class TestCleanupExcessCount:
    def test_oldest_sessions_removed_when_count_exceeded(self, db_path):
        """T-CL02: 세션 수 > max_count → 가장 오래된 세션부터 삭제."""
        _insert_old_session(db_path, "s1", days_ago=90)
        _insert_old_session(db_path, "s2", days_ago=60)
        _insert_old_session(db_path, "s3", days_ago=30)

        n = cleanup_if_needed(
            db_path, "current", max_age_days=0, max_count=2, policy="delete"
        )

        assert n == 1
        assert not _session_exists(db_path, "s1")
        assert _session_exists(db_path, "s2")
        assert _session_exists(db_path, "s3")


# ---------------------------------------------------------------------------
# T-CL03: 현재 session_id 보호
# ---------------------------------------------------------------------------


class TestCleanupProtectCurrent:
    def test_current_session_not_deleted(self, db_path):
        """T-CL03: current session_id는 age 초과여도 삭제 대상에서 제외된다."""
        _insert_old_session(db_path, "current_old", days_ago=60)

        n = cleanup_if_needed(
            db_path, "current_old", max_age_days=30, max_count=0, policy="delete"
        )

        assert n == 0
        assert _session_exists(db_path, "current_old")


# ---------------------------------------------------------------------------
# T-CL04: archive 정책 — 파일 생성 + 주 DB에서 제거
# ---------------------------------------------------------------------------


class TestCleanupArchivePolicy:
    def test_archive_policy_creates_file_and_removes_from_main(self, db_path):
        """T-CL04: archive 정책 하에서 아카이브 파일 생성 + 주 DB 제거."""
        _insert_old_session(db_path, "old_session", days_ago=60)

        n = cleanup_if_needed(
            db_path, "current", max_age_days=30, max_count=0, policy="archive"
        )

        assert n == 1
        assert not _session_exists(db_path, "old_session")

        archive_path = get_archive_db_path(db_path)
        with contextlib.closing(_db(archive_path)) as arc:
            row = arc.execute(
                "SELECT id FROM sessions WHERE id='old_session'"
            ).fetchone()
        assert row is not None


# ---------------------------------------------------------------------------
# T-CL05: archive → payload 복원 가능
# ---------------------------------------------------------------------------


class TestCleanupArchiveRestorability:
    def test_archived_payload_is_restorable(self, db_path):
        """T-CL05: 아카이브된 세션의 ccr_store에서 원본 payload를 복원할 수 있다."""
        original = "x" * 80
        _insert_old_session(db_path, "old_session", days_ago=60)
        with contextlib.closing(_db(db_path)) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO nodes (session_id, name, thought_type, payload, "
                    "ccr_hash, status, tokens_original, tokens_saved) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ("old_session", "n1", "Objective", original, "a" * 24, "COMPLETED", 20, 0),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO ccr_store (hash, session_id, node_name, original) "
                    "VALUES (?, ?, ?, ?)",
                    ("a" * 24, "old_session", "n1", original),
                )

        cleanup_if_needed(
            db_path, "current", max_age_days=30, max_count=0, policy="archive"
        )

        archive_path = get_archive_db_path(db_path)
        with contextlib.closing(_db(archive_path)) as arc:
            row = arc.execute(
                "SELECT original FROM ccr_store WHERE session_id='old_session'"
            ).fetchone()
        assert row is not None
        assert row["original"] == original


# ---------------------------------------------------------------------------
# T-CL06: 조건 미충족 시 no-op
# ---------------------------------------------------------------------------


class TestCleanupNoOp:
    def test_no_cleanup_when_conditions_not_met(self, db_path):
        """T-CL06: age/count 조건 모두 미충족 시 cleanup이 실행되지 않는다."""
        _insert_old_session(db_path, "recent", days_ago=5)

        n = cleanup_if_needed(
            db_path, "current", max_age_days=365, max_count=500, policy="delete"
        )

        assert n == 0
        assert _session_exists(db_path, "recent")


# ---------------------------------------------------------------------------
# T-CL07: 반환값 = 삭제된 세션 수
# ---------------------------------------------------------------------------


class TestCleanupReturnCount:
    def test_return_value_equals_deleted_count(self, db_path):
        """T-CL07: cleanup_if_needed 반환값이 삭제된 세션 수와 정확히 일치한다."""
        _insert_old_session(db_path, "s1", days_ago=90)
        _insert_old_session(db_path, "s2", days_ago=60)
        _insert_old_session(db_path, "s3", days_ago=45)

        n = cleanup_if_needed(
            db_path, "current", max_age_days=30, max_count=0, policy="delete"
        )

        assert n == 3


# ---------------------------------------------------------------------------
# 에러 케이스
# ---------------------------------------------------------------------------


class TestCleanupErrors:
    def test_invalid_policy_raises_value_error(self, db_path):
        """잘못된 policy → ValueError."""
        with pytest.raises(ValueError, match="policy"):
            cleanup_if_needed(db_path, "s", policy="compress")
