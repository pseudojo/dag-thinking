"""
prepare_release.py — §4.2 릴리스 검증 파이프라인.

L1-L4: check_loc_limits — 파일 LOC 한도 검사
G1-G3: check_git_clean — 소스 컨트롤 상태 검사
R1-R3: check_ruff — §4.2-3 정적 분석 (v0.32 신규)
A1-A4: check_audit — §4.2-2 공급망 감사 + SBOM (v0.33 신규)
T1-T2: run_tests — pytest 서브프로세스 실행
S1: smoke_test — in-memory MCP 라이프사이클 검증
M1-M2: main — 6종 체크 + 종합 exit code
"""

import asyncio
import subprocess
from types import SimpleNamespace

import prepare_release
from prepare_release import (
    check_audit,
    check_git_clean,
    check_loc_limits,
    check_ruff,
    main,
    run_tests,
    smoke_test,
)


def _git(repo: str, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t.t", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


class TestCheckLocLimits:
    def test_l1_files_under_limit_return_empty(self, tmp_path):
        """L1: 한도 내 파일만 → []."""
        (tmp_path / "small.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
        assert check_loc_limits(str(tmp_path), max_loc=500) == []

    def test_l2_file_over_limit_detected(self, tmp_path):
        """L2: 501줄 파일, max=500 → 해당 파일 경로 포함."""
        big = tmp_path / "big.py"
        big.write_text("\n".join(f"x{i} = {i}" for i in range(501)), encoding="utf-8")
        violations = check_loc_limits(str(tmp_path), max_loc=500)
        assert violations == [str(big)]

    def test_l3_boundary_exactly_max_loc_passes(self, tmp_path):
        """L3: 정확히 500줄, max=500 → 통과 (미포함)."""
        edge = tmp_path / "edge.py"
        edge.write_text("\n".join(f"x{i} = {i}" for i in range(500)), encoding="utf-8")
        assert check_loc_limits(str(tmp_path), max_loc=500) == []

    def test_l4_empty_dir_returns_empty(self, tmp_path):
        """L4: 빈 디렉토리 → []."""
        assert check_loc_limits(str(tmp_path), max_loc=500) == []


class TestCheckGitClean:
    def test_g1_clean_repo_returns_true(self, tmp_path):
        """G1: 커밋 완료된 clean repo → (True, ...)."""
        repo = str(tmp_path)
        _git(repo, "init")
        (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "init")
        ok, detail = check_git_clean(repo)
        assert ok is True, f"clean repo는 True 필요, detail: {detail}"

    def test_g2_dirty_repo_returns_false_with_filename(self, tmp_path):
        """G2: 미추적 파일 존재 → (False, 파일명 포함 메시지)."""
        repo = str(tmp_path)
        _git(repo, "init")
        (tmp_path / "untracked.txt").write_text("dirty\n", encoding="utf-8")
        ok, detail = check_git_clean(repo)
        assert ok is False
        assert "untracked.txt" in detail, f"detail에 파일명 포함 필요, 실제: {detail}"

    def test_g3_non_git_dir_returns_false(self, tmp_path):
        """G3: 비-git 디렉토리 → (False, ...) — 예외 raise 대신 tuple 반환."""
        ok, detail = check_git_clean(str(tmp_path))
        assert ok is False
        assert isinstance(detail, str) and detail


class TestCheckRuff:
    """R1-R3: check_ruff — §4.2-3 정적 분석. --no-sync로 uv 재설치 차단."""

    def test_r1_clean_src_returns_true(self, monkeypatch):
        """R1: ruff 종료코드 0 → (True, ...). --no-sync 플래그 포함 확인."""
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(prepare_release.subprocess, "run", fake_run)
        ok, detail = check_ruff("src")
        assert ok is True
        assert "--no-sync" in captured["cmd"], (
            f"--no-sync 없으면 uv가 잠긴 exe 재설치 시도: {captured['cmd']}"
        )

    def test_r2_violations_return_false_with_output(self, monkeypatch):
        """R2: 위반 존재 → (False, 위반 내용 포함)."""
        monkeypatch.setattr(
            prepare_release.subprocess,
            "run",
            lambda cmd, **kw: SimpleNamespace(
                returncode=1, stdout="src/x.py:1:1: E501 line too long\n", stderr=""
            ),
        )
        ok, detail = check_ruff("src")
        assert ok is False
        assert "E501" in detail

    def test_r3_missing_tool_returns_false(self, monkeypatch):
        """R3: 실행 자체 실패(OSError) → (False, 사유) — 예외 전파 금지."""

        def boom(cmd, **kw):
            raise OSError("uv not found")

        monkeypatch.setattr(prepare_release.subprocess, "run", boom)
        ok, detail = check_ruff("src")
        assert ok is False
        assert "failed" in detail

    def test_r4_lints_src_and_tests(self, monkeypatch):
        """R4(TD-14): 다중 타겟 — src와 tests 두 경로가 모두 ruff cmd에 전달된다."""
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(prepare_release.subprocess, "run", fake_run)
        ok, _ = check_ruff("src", "tests")
        assert ok is True
        assert "src" in captured["cmd"]
        assert "tests" in captured["cmd"]
        assert "--no-sync" in captured["cmd"]


class TestCheckAudit:
    """A1-A4: check_audit — §4.2-2 공급망 취약점 감사 + SBOM (PLAN.md §13.4)."""

    def test_a1_missing_tool_returns_false(self, monkeypatch):
        """A1: 실행 자체 실패(OSError: uv/uvx 부재) → (False, 사유) — 예외 전파 금지."""

        def boom(cmd, **kw):
            raise OSError("uv not found")

        monkeypatch.setattr(prepare_release.subprocess, "run", boom)
        ok, detail = check_audit(".")
        assert ok is False
        assert "audit execution failed" in detail

    def test_a2_export_failure_returns_false(self, monkeypatch):
        """A2: uv export 비0 종료(비-프로젝트 등) → (False, stderr 포함)."""
        monkeypatch.setattr(
            prepare_release.subprocess,
            "run",
            lambda cmd, **kw: SimpleNamespace(
                returncode=2, stdout="", stderr="error: No `pyproject.toml` found\n"
            ),
        )
        ok, detail = check_audit(".")
        assert ok is False
        assert "No `pyproject.toml` found" in detail

    def test_a3_clean_audit_returns_true_with_sbom(self, monkeypatch):
        """A3: export·audit 모두 성공 → (True, SBOM 경로 포함). 핵심 플래그 검증."""
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(prepare_release.subprocess, "run", fake_run)
        ok, detail = check_audit(".", sbom_path="sbom.json")
        assert ok is True
        assert "sbom.json" in detail
        export_cmd, audit_cmd = calls
        assert "--frozen" in export_cmd, "uv export는 --frozen 필수 — lock 갱신/sync 차단"
        assert audit_cmd[:2] == ["uvx", "pip-audit"]
        assert "--no-deps" in audit_cmd, "uv export가 전이 의존성 전체 포함 — 재해석 차단"
        assert "cyclonedx-json" in audit_cmd, "SBOM은 CycloneDX 형식 (§4.2-2)"

    def test_a4_vulnerabilities_return_false_with_detail(self, monkeypatch):
        """A4: pip-audit 비0 종료(취약점 발견) → (False, 감사 출력 포함) — blocking audit."""
        results = iter(
            [
                SimpleNamespace(returncode=0, stdout="", stderr=""),  # uv export
                SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr="Found 2 known vulnerabilities in 1 package\n",
                ),  # pip-audit
            ]
        )
        monkeypatch.setattr(prepare_release.subprocess, "run", lambda cmd, **kw: next(results))
        ok, detail = check_audit(".")
        assert ok is False
        assert "vulnerabilities" in detail


class TestRunTests:
    def test_t1_passing_project_returns_true(self, tmp_path):
        """T1: 통과 테스트만 있는 tmp 프로젝트 → (True, ...)."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        ok, detail = run_tests(str(tmp_path))
        assert ok is True, f"통과 프로젝트는 True 필요, detail: {detail}"

    def test_t2_failing_project_returns_false(self, tmp_path):
        """T2: 실패 테스트 포함 tmp 프로젝트 → (False, ...)."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_bad.py").write_text(
            "def test_bad():\n    assert False\n", encoding="utf-8"
        )
        ok, detail = run_tests(str(tmp_path))
        assert ok is False
        assert isinstance(detail, str) and detail


class TestSmokeTest:
    def test_s1_real_server_smoke_passes(self):
        """S1: 실제 서버 — list_tools == ['dag_thinking'] + info 호출 성공 → (True, ...).

        §4.2 Smoke Testing: 연결 초기화 → List Tools 스키마 발견 → payload 실행 검증.
        """
        ok, detail = asyncio.run(smoke_test())
        assert ok is True, f"smoke test 실패: {detail}"
        assert "dag_thinking" in detail


async def _fake_smoke_ok() -> tuple[bool, str]:
    return True, "smoke ok"


class TestMain:
    def _patch_all_pass(self, monkeypatch):
        monkeypatch.setattr(prepare_release, "check_git_clean", lambda repo: (True, "clean"))
        monkeypatch.setattr(prepare_release, "check_loc_limits", lambda src, max_loc=500: [])
        monkeypatch.setattr(prepare_release, "check_ruff", lambda *targets: (True, "no violations"))
        monkeypatch.setattr(
            prepare_release,
            "check_audit",
            lambda repo, sbom_path="sbom.json": (True, "no known vulnerabilities"),
        )
        monkeypatch.setattr(prepare_release, "run_tests", lambda repo: (True, "123 passed"))
        monkeypatch.setattr(prepare_release, "smoke_test", _fake_smoke_ok)

    def test_m1_all_pass_six_checks_exit_zero(self, monkeypatch, capsys):
        """M1(M0 통합): 전 체크 통과 → exit 0, 6종 [PASS](ruff·audit 포함), [FAIL] 없음."""
        self._patch_all_pass(monkeypatch)
        assert main() == 0
        out = capsys.readouterr().out
        assert out.count("[PASS]") == 6
        assert "[FAIL]" not in out
        assert "ruff" in out
        assert "audit" in out

    def test_m2_one_check_fails_returns_one(self, monkeypatch, capsys):
        """M2: 체크 1종 실패 → main() == 1, [FAIL] 출력."""
        self._patch_all_pass(monkeypatch)
        monkeypatch.setattr(
            prepare_release, "run_tests", lambda repo: (False, "2 failed, 441 passed")
        )
        assert main() == 1
        assert "[FAIL]" in capsys.readouterr().out
