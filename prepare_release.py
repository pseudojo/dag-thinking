"""prepare_release — MCP Best Practices §4.2 release validation pipeline.

Standard library + fastmcp (existing dependency) only.
CLI script (not the MCP server process) — stdout output is permitted here.
"""

import asyncio
import subprocess
import sys
from pathlib import Path


def check_git_clean(repo_dir: str) -> tuple[bool, str]:
    """git working tree 상태 검사 — clean이면 (True, ...), 더티/비-repo면 (False, 사유)."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"git execution failed: {e}"
    if result.returncode != 0:
        return False, result.stderr.strip() or "git status failed"
    if not result.stdout.strip():
        return True, "working tree clean"
    return False, f"uncommitted changes:\n{result.stdout.strip()}"


def check_loc_limits(src_dir: str, max_loc: int = 500) -> list[str]:
    """src_dir 내 *.py 중 총 라인 수가 max_loc를 초과하는 파일 경로 목록 (정렬)."""
    violations: list[str] = []
    for py_file in sorted(Path(src_dir).glob("*.py")):
        loc = len(py_file.read_text(encoding="utf-8").splitlines())
        if loc > max_loc:
            violations.append(str(py_file))
    return violations


def check_ruff(src_dir: str) -> tuple[bool, str]:
    """§4.2-3 정적 분석 — ruff check. --no-sync: uv가 잠긴 exe 재설치를 시도하지 않도록 차단."""
    try:
        result = subprocess.run(
            ["uv", "run", "--no-sync", "ruff", "check", src_dir],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"ruff execution failed: {e}"
    if result.returncode == 0:
        return True, "no lint violations"
    lines = result.stdout.strip().splitlines()
    tail = "\n".join(lines[-20:]) if lines else result.stderr.strip()
    return False, tail


def run_tests(repo_dir: str) -> tuple[bool, str]:
    """pytest tests/ -q 서브프로세스 실행 — 종료코드 0이면 (True, 요약), 아니면 (False, 출력 끝)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"pytest execution failed: {e}"
    lines = result.stdout.strip().splitlines()
    if result.returncode == 0:
        return True, lines[-1] if lines else "tests passed"
    tail = "\n".join(lines[-20:]) if lines else result.stderr.strip()
    return False, tail


async def smoke_test() -> tuple[bool, str]:
    """§4.2 Smoke Testing — in-memory 클라이언트로 MCP 라이프사이클 전체 검증.

    연결 초기화 → List Tools 스키마 발견 → action='info' payload 실행.
    """
    from fastmcp import Client

    from src.server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        if tool_names != ["dag_thinking"]:
            return False, f"expected single tool ['dag_thinking'], got {tool_names}"

        result = await client.call_tool("dag_thinking", {"action": "info"}, raise_on_error=False)
        if result.is_error:
            return False, f"action='info' returned error: {result.content}"

    return True, "smoke test passed: tool 'dag_thinking' discovered, info action executed"


def main() -> int:
    """§4.2 검증 5종 순차 실행 — 전부 통과 0, 하나라도 실패 1."""
    repo_dir = str(Path(__file__).parent)
    src_dir = str(Path(__file__).parent / "src")

    loc_violations = check_loc_limits(src_dir)
    checks: list[tuple[str, bool, str]] = [
        ("source control", *check_git_clean(repo_dir)),
        (
            "LOC limits (<=500)",
            not loc_violations,
            "all files within limit" if not loc_violations else ", ".join(loc_violations),
        ),
        ("static analysis (ruff)", *check_ruff(src_dir)),
        ("test suite", *run_tests(repo_dir)),
        ("MCP smoke test", *asyncio.run(smoke_test())),
    ]

    all_ok = True
    for name, ok, detail in checks:
        print(f"{'[PASS]' if ok else '[FAIL]'} {name}: {detail}")
        if not ok:
            all_ok = False
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
