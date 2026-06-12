"""action='status' 행위 테스트 — 토폴로지, 메트릭, 복원 매니페스트, dag_health.

PLAN.md §3 status 명세 + §8 체크리스트 C14~C15, C22~C25, C38~C41 커버.
"""

from tests.helpers import invalidate, status, think


class TestTopology:
    def test_empty_session_shape(self, db_path):
        """C14: 노드 0개여도 전체 응답 구조 유지."""
        s = status(db_path, "empty")
        assert s["session_id"] == "empty"
        assert s["dag"] == {"nodes": [], "edges": []}
        assert s["restoration_manifest"]["nodes"] == []
        assert "how_to_restore" in s["restoration_manifest"]

    def test_nodes_carry_full_fields(self, db_path):
        """C25/I43: 노드 항목에 name/thought_type/status/created_at/ccr_hash."""
        think(db_path, "s1", "root", "Objective")
        node = status(db_path, "s1")["dag"]["nodes"][0]
        assert node["name"] == "root"
        assert node["thought_type"] == "Objective"
        assert node["status"] == "COMPLETED"
        assert isinstance(node["created_at"], str) and node["created_at"]
        assert isinstance(node["ccr_hash"], str)

    def test_edges_reflect_depends_on(self, db_path):
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        assert status(db_path, "s1")["dag"]["edges"] == [{"parent": "a", "child": "b"}]


class TestMetrics:
    def test_metrics_formula(self, db_path):
        """C22/C23: tokens_compressed = original - saved, ratio 공식."""
        think(db_path, "s1", "n1", "Objective")
        think(db_path, "s1", "n2", "Hypothesis")
        m = status(db_path, "s1")["metrics"]
        assert m["tokens_original"] > 0
        assert m["tokens_compressed"] == m["tokens_original"] - m["tokens_saved"]
        expected_ratio = 1 - m["tokens_compressed"] / m["tokens_original"]
        assert abs(m["ratio"] - round(expected_ratio, 4)) < 1e-9

    def test_invalidated_nodes_excluded_from_metrics(self, db_path):
        """P2-4: INVALIDATED 노드는 메트릭에서 제외."""
        think(db_path, "s1", "keep", "Objective")
        think(db_path, "s1", "drop", "Hypothesis")
        baseline = status(db_path, "s1")["metrics"]["tokens_original"]
        invalidate(db_path, "s1", "drop")
        after = status(db_path, "s1")["metrics"]["tokens_original"]
        assert after < baseline


class TestRestorationManifest:
    def test_restore_cmd_exact_format(self, db_path):
        """C15/P3-1: restore_cmd가 호출 가능한 형식과 정확히 일치."""
        r = think(db_path, "s1", "root", "Objective")
        entry = status(db_path, "s1")["restoration_manifest"]["nodes"][0]
        expected = (
            f"dag_thinking(action='restore', session_id={'s1'!r}, ccr_hash={r['ccr_hash']!r})"
        )
        assert entry["restore_cmd"] == expected
        assert entry["name"] == "root"
        assert entry["ccr_hash"] == r["ccr_hash"]

    def test_restore_cmd_quote_safe(self, db_path):
        """P1-3: 작은따옴표 포함 session_id도 valid Python 인자 형태."""
        sid = "it's_a_session"
        think(db_path, sid, "root", "Objective")
        cmd = status(db_path, sid)["restoration_manifest"]["nodes"][0]["restore_cmd"]
        assert repr(sid) in cmd


class TestDagHealth:
    def test_empty_session_health(self, db_path):
        """빈 세션 — total 0, Objective 시작 안내."""
        h = status(db_path, "empty")["dag_health"]
        assert h["total_nodes"] == 0
        assert h["is_converging"] is False
        assert h["max_depth"] == 0
        assert h["orphan_nodes"] == []
        assert "Objective" in h["health_hint"]

    def test_converging_requires_synthesis_or_action(self, db_path):
        """C39/IC26: Synthesis 등장 전 False, 후 True."""
        think(db_path, "s1", "a", "Objective")
        assert status(db_path, "s1")["dag_health"]["is_converging"] is False
        think(db_path, "s1", "syn", "Synthesis", depends_on=["a"])
        assert status(db_path, "s1")["dag_health"]["is_converging"] is True

    def test_chain_max_depth(self, db_path):
        """C40: A→B→C 체인 → max_depth=2."""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        think(db_path, "s1", "c", "Evidence", depends_on=["b"])
        assert status(db_path, "s1")["dag_health"]["max_depth"] == 2

    def test_orphan_detection(self, db_path):
        """C41: 연결 없는 2개 노드 → 모두 고아."""
        think(db_path, "s1", "x", "Objective")
        think(db_path, "s1", "y", "Hypothesis")
        assert status(db_path, "s1")["dag_health"]["orphan_nodes"] == ["x", "y"]

    def test_single_node_not_orphan(self, db_path):
        """엣지: 1-노드 세션은 고아 판정 제외."""
        think(db_path, "s1", "only", "Objective")
        assert status(db_path, "s1")["dag_health"]["orphan_nodes"] == []

    def test_type_distribution_excludes_invalidated(self, db_path):
        """P2-1: INVALIDATED 노드는 type 분포·total에서 제외."""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Synthesis", depends_on=["a"])
        invalidate(db_path, "s1", "a")  # cascade → b도 무효화
        h = status(db_path, "s1")["dag_health"]
        assert h["thought_type_distribution"] == {}
        assert h["total_nodes"] == 0
        assert h["is_converging"] is False

    def test_invalidated_edges_excluded_from_depth(self, db_path):
        """I10: INVALIDATED 노드 경유 경로는 depth 계산에서 제외."""
        think(db_path, "s1", "a", "Objective")
        think(db_path, "s1", "b", "Hypothesis", depends_on=["a"])
        think(db_path, "s1", "c", "Evidence", depends_on=["b"])
        invalidate(db_path, "s1", "b")  # b, c 무효화 → a만 남음
        h = status(db_path, "s1")["dag_health"]
        assert h["max_depth"] == 0
        assert h["total_nodes"] == 1
