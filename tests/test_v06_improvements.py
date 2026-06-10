"""
v0.6 improvements — RED phase tests.

Covers:
  R-EDGE: edge deletion direction fix (parent→child) in upsert
  R-CCR:  ccr_store composite PK + INSERT OR IGNORE
"""

import sqlite3

from tests.helpers import invalidate, restore, status, think

PAYLOAD_A = (
    "The key objective is to reduce system latency. "
    "Critical finding: database connection pooling is misconfigured. "
    "Therefore we must reconfigure the pool size to resolve this issue. "
    "The assumption is that pool size of 20 handles peak load. "
    "This conclusion is supported by profiling data from production."
)

PAYLOAD_B = (
    "Hypothesis: increasing pool size from 5 to 20 will cut latency by 70%. "
    "Evidence from load testing confirms that connection wait time dominates. "
    "The risk is memory pressure at peak — must monitor. "
    "Therefore the result is a net positive with careful rollout. "
    "This assumption holds under current traffic patterns."
)

PAYLOAD_X = (
    "Assumption: traffic will not exceed 500 RPS during the migration window. "
    "Key evidence from monitoring shows p99 never exceeded 350 RPS in past 90 days. "
    "The conclusion is that this assumption is well-grounded and safe. "
    "Therefore the migration can proceed without traffic shaping. "
    "This finding is critical for the rollout plan."
)


# ---------------------------------------------------------------------------
# R-EDGE: edge deletion direction
# ---------------------------------------------------------------------------

class TestEdgeDeletionDirection:
    """R-E-1 ~ R-E-4: verify that updating a node resets only its OWN incoming
    edges (child side), not its outgoing edges (parent side)."""

    def test_update_parent_preserves_child_edge(self, db_path):
        """R-E-1: A→B exists; update A with depends_on=[] → A→B must still exist."""
        think(db_path, "s1", "node_a", "Objective", PAYLOAD_A)
        think(db_path, "s1", "node_b", "Hypothesis", PAYLOAD_B, depends_on=["node_a"])

        # Update A — should NOT erase the A→B edge
        think(db_path, "s1", "node_a", "Objective", PAYLOAD_A, depends_on=[])

        s = status(db_path, "s1")
        edges = {(e["parent"], e["child"]) for e in s["dag"]["edges"]}
        assert ("node_a", "node_b") in edges, (
            "Updating node_a must not delete the node_a→node_b edge"
        )

    def test_update_parent_with_new_dep_preserves_child_edge(self, db_path):
        """R-E-2: A→B exists; update A with depends_on=[X] → X→A added, A→B preserved."""
        think(db_path, "s1", "node_a", "Objective", PAYLOAD_A)
        think(db_path, "s1", "node_b", "Hypothesis", PAYLOAD_B, depends_on=["node_a"])
        think(db_path, "s1", "node_x", "Assumption", PAYLOAD_X)

        think(db_path, "s1", "node_a", "Objective", PAYLOAD_A, depends_on=["node_x"])

        s = status(db_path, "s1")
        edges = {(e["parent"], e["child"]) for e in s["dag"]["edges"]}
        assert ("node_x", "node_a") in edges, "X→A edge must be added"
        assert ("node_a", "node_b") in edges, "A→B edge must not be deleted"

    def test_update_child_resets_own_incoming_edge(self, db_path):
        """R-E-3: B depends_on=[A]; update B with depends_on=[X] → X→B, A→B gone."""
        think(db_path, "s1", "node_a", "Objective", PAYLOAD_A)
        think(db_path, "s1", "node_x", "Assumption", PAYLOAD_X)
        think(db_path, "s1", "node_b", "Hypothesis", PAYLOAD_B, depends_on=["node_a"])

        think(db_path, "s1", "node_b", "Hypothesis", PAYLOAD_B, depends_on=["node_x"])

        s = status(db_path, "s1")
        edges = {(e["parent"], e["child"]) for e in s["dag"]["edges"]}
        assert ("node_x", "node_b") in edges, "X→B edge must exist after update"
        assert ("node_a", "node_b") not in edges, "A→B edge must be removed after B's update"

    def test_cascade_invalidate_follows_correct_edges_after_parent_update(self, db_path):
        """R-E-4: A→B; update A; invalidate(A) must still cascade to B."""
        think(db_path, "s1", "node_a", "Objective", PAYLOAD_A)
        think(db_path, "s1", "node_b", "Hypothesis", PAYLOAD_B, depends_on=["node_a"])

        # Update A without changing structure
        think(db_path, "s1", "node_a", "Objective", PAYLOAD_X, depends_on=[])

        result = invalidate(db_path, "s1", "node_a")
        assert "node_b" in result["invalidated"], (
            "Cascade invalidate must reach node_b via A→B edge after A is updated"
        )


# ---------------------------------------------------------------------------
# R-CCR: ccr_store hash collision fix
# ---------------------------------------------------------------------------

class TestCcrStoreHashCollision:
    """R-C-1 ~ R-C-4: verify composite PK + INSERT OR IGNORE semantics."""

    def _ccr_store_rows(self, db_path: str, hash_val: str) -> list[dict]:
        """Helper: fetch all ccr_store rows for a given hash."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT hash, session_id, node_name FROM ccr_store WHERE hash=?",
            (hash_val,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def test_same_session_same_content_idempotent(self, db_path):
        """R-C-1: OR IGNORE — duplicate think in same session doesn't raise and restores OK."""
        r1 = think(db_path, "s1", "node_a", "Objective", PAYLOAD_A)
        h = r1["ccr_hash"]
        # Same content, same session, different node name — same hash
        r2 = think(db_path, "s1", "node_a", "Objective", PAYLOAD_A)
        assert r2["ccr_hash"] == h
        restored = restore(db_path, "s1", h)
        assert restored["original_payload"] == PAYLOAD_A

    def test_two_sessions_same_content_both_restore(self, db_path):
        """R-C-2: S1 and S2 share identical content → both can restore independently."""
        r1 = think(db_path, "s1", "node_a", "Objective", PAYLOAD_A)
        r2 = think(db_path, "s2", "node_a", "Objective", PAYLOAD_A)
        # Same content → same hash
        assert r1["ccr_hash"] == r2["ccr_hash"]
        h = r1["ccr_hash"]

        # Both sessions must be able to restore
        res1 = restore(db_path, "s1", h)
        res2 = restore(db_path, "s2", h)
        assert res1["original_payload"] == PAYLOAD_A
        assert res2["original_payload"] == PAYLOAD_A

    def test_s1_update_does_not_break_s2_restore(self, db_path):
        """R-C-3: S1 updates its node (new content) → S2's original hash still restores."""
        r1 = think(db_path, "s1", "node_a", "Objective", PAYLOAD_A)
        r2 = think(db_path, "s2", "node_a", "Objective", PAYLOAD_A)
        shared_hash = r1["ccr_hash"]
        assert shared_hash == r2["ccr_hash"]

        # S1 now updates node_a with different content
        think(db_path, "s1", "node_a", "Objective", PAYLOAD_B)

        # S2 must still restore the original shared hash
        res2 = restore(db_path, "s2", shared_hash)
        assert res2["original_payload"] == PAYLOAD_A, (
            "S2's restore must succeed even after S1 updated its node"
        )

    def test_old_hash_not_deleted_after_update(self, db_path):
        """R-C-4: After S1 updates (changing content), old hash remains in ccr_store."""
        r1 = think(db_path, "s1", "node_a", "Objective", PAYLOAD_A)
        old_hash = r1["ccr_hash"]

        # Update with different content
        r2 = think(db_path, "s1", "node_a", "Objective", PAYLOAD_B)
        new_hash = r2["ccr_hash"]
        assert old_hash != new_hash

        rows = self._ccr_store_rows(db_path, old_hash)
        assert len(rows) >= 1, (
            f"Old hash {old_hash!r} must remain in ccr_store after node update"
        )
