# dag-thinking

DAG 구조 추론과 CCR(Compress-Cache-Retrieve) 컨텍스트 압축을 단일 진입점으로 결합한 경량 MCP 서버.

## 개요

LLM이 긴 세션에서 구조화된 추론을 수행할 때 두 가지 문제가 발생합니다.

1. **컨텍스트 누적**: 추론 노드가 쌓일수록 `resolve_uris` 비용이 선형으로 증가
2. **툴 건너뛰기**: 여러 툴이 노출되면 LLM이 필수 단계를 생략

dag-thinking은 단일 툴 `dag_thinking(action=...)` 하나만 노출해 잘못된 선택을 구조적으로 차단하고, `depends_on` 지정 시 부모 컨텍스트를 자동 내장해 별도 resolve 호출을 없앱니다.

## 주요 특징

- **단일 진입점**: MCP 툴 1개(`dag_thinking`) — `action` 파라미터로 분기
- **자동 컨텍스트 내장**: `depends_on` 지정 시 부모 노드의 압축 페이로드를 응답에 자동 첨부
- **완전한 가역성**: `status` 응답에 항상 복원 매니페스트 포함, 복붙 가능한 복원 명령어 제공
- **thought_type별 압축 최적화**: Evidence, Synthesis 등 타입 특화 키워드로 중요 문장 우선 보존
- **컨텍스트 압박 경보**: 세션 누적 토큰 수 기반 `low / medium / high` 경보
- **DAG 수렴 진단**: 고립 노드 감지, 최장 체인 깊이, 수렴 여부 실시간 진단
- **ML 의존성 없음**: 표준 라이브러리 + `fastmcp` + `pydantic`만 사용

## 설치

```bash
# 의존성 설치 (uv 권장)
uv sync

# 또는 pip
pip install -e .
```

**요구사항**: Python ≥ 3.13

## MCP 설정

`claude_desktop_config.json` 또는 MCP 설정 파일에 추가:

```json
{
  "mcpServers": {
    "dag-thinking": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/dag-thinking", "dag-thinking"]
    }
  }
}
```

## 사용법

### 단일 툴 인터페이스

```python
dag_thinking(
    action: "think" | "status" | "invalidate" | "restore" | "info",
    session_id: str,          # action="info"는 생략 가능

    # action="think" 전용
    node_name: str | None,
    thought_type: "Objective" | "Hypothesis" | "Assumption"
               | "Evidence" | "Critique" | "Synthesis" | "Action" | None,
    payload: str | None,       # 80–1500자
    depends_on: list[str],     # 부모 노드 → 응답에 parent_context 자동 첨부
    note: str,                 # 압축 제외 스크래치패드

    # action="invalidate" 전용
    target_node: str | None,
    reason: str,

    # action="restore" 전용
    ccr_hash: str | None,      # None이면 세션 전체 목록 반환
)
```

### action별 동작

#### `think` — 추론 노드 생성/갱신

```python
dag_thinking(
    action="think",
    session_id="my_session",
    node_name="define_problem",
    thought_type="Objective",
    payload="성능 저하의 근본 원인을 분석해야 한다. ...",
)
```

응답:
```json
{
  "status": "created",
  "node": "define_problem",
  "ccr_hash": "a3f8c2d1e5b9f0a2c7d4",
  "compression": { "tokens_saved": 42, "session_total_saved": 42 },
  "next_hint": "Add Hypothesis or Assumption nodes to explore this objective.",
  "context_pressure": { "level": "low", "tokens_original": 42, "hint": "..." }
}
```

`depends_on` 지정 시 `parent_context` 자동 첨부:
```python
dag_thinking(
    action="think",
    session_id="my_session",
    node_name="hypothesis_1",
    thought_type="Hypothesis",
    payload="비동기 DB 호출로 전환하면 p99 레이턴시가 60% 감소할 것이다. ...",
    depends_on=["define_problem"],
)
# → 응답에 parent_context.define_problem.payload 자동 포함
```

#### `status` — DAG 현황 조회

```python
dag_thinking(action="status", session_id="my_session")
```

응답에 포함되는 정보:
- `dag.nodes` / `dag.edges` — 전체 토폴로지 (각 노드에 `created_at` 포함)
- `metrics` — 원본/압축 토큰 수, 절약량, 압축률
- `restoration_manifest` — 복원 명령어 목록 (항상 포함)
- `dag_health` — 수렴 여부, 최장 체인 깊이, 고립 노드

#### `invalidate` — 노드 및 하위 노드 무효화

```python
dag_thinking(
    action="invalidate",
    session_id="my_session",
    target_node="hypothesis_1",
    reason="전제 조건 오류",
)
# A→B→C 구조에서 A invalidate 시 B, C도 INVALIDATED
```

#### `restore` — 원본 페이로드 복원

```python
# hash 없이 호출 → 세션 내 복원 가능 노드 목록
dag_thinking(action="restore", session_id="my_session")

# hash 지정 → 압축 전 원본 반환 (byte-level 동일)
dag_thinking(action="restore", session_id="my_session", ccr_hash="a3f8c2d1e5b9f0a2c7d4")
```

#### `info` — 서버 진단 (MCP Best Practices §3.2)

```python
dag_thinking(action="info")  # session_id 불필요
```

응답: 서버명, 동적 버전(pyproject.toml 기준), DB 경로/존재 여부, 사용 가능한 액션 목록.

### MCP Resource

세션 상태는 읽기 전용 Resource로도 노출됩니다:

```
dag-thinking-session://{session_id}
```

### thought_type 가이드

| thought_type | 용도 | 다음 권장 타입 |
|---|---|---|
| `Objective` | 분석 목표 정의 | Hypothesis, Assumption |
| `Hypothesis` | 검증할 가설 제시 | Evidence, Assumption |
| `Assumption` | 전제 조건 명시 | Evidence, Critique |
| `Evidence` | 데이터/실험 결과 | Synthesis, Critique |
| `Critique` | 약점/반론 제기 | Synthesis |
| `Synthesis` | 결론 도출 | Action |
| `Action` | 실행 계획 | status() 호출 |

### 컨텍스트 압박 경보

| level | 조건 | 권장 행동 |
|---|---|---|
| `low` | `tokens_original` < 900 | 추론 계속 |
| `medium` | 900 ≤ `tokens_original` < 1700 | Synthesis 검토 권장 |
| `high` | `tokens_original` ≥ 1700 | 즉시 수렴 권고 |

## 아키텍처

```
dag-thinking/
├── src/
│   ├── server.py        # FastMCP 얇은 레이어 — 단일 툴, MCP Resource, 에러 변환
│   ├── actions.py       # 비즈니스 로직 — status/invalidate/restore/info + dispatcher
│   ├── think.py         # think 액션 — 검증, 사이클 감지, DAG 진단, 압박 경보
│   ├── db.py            # DB 프리미티브 — 스키마, 연결, 그래프 유틸리티
│   └── compressor.py    # 순수 Python extractive 압축기
├── tests/               # 행위 기준 8개 파일, 130 tests
│   ├── tools/           # 개발 툴 테스트 (prepare_release.py)
│   └── eval/            # LLM 연동 평가 하네스 (EvalHarness)
├── docs/                # CHANGELOG · IMPROVEMENTS · EVAL_PLAN · MCP Best Practices
├── prepare_release.py   # 릴리스 검증 파이프라인 — git/LOC/ruff/pip-audit+SBOM/tests/MCP smoke
└── pyproject.toml
```

모든 소스 파일은 500 LOC 미만을 유지하며 (MCP Best Practices §4.2), `prepare_release.py`가 릴리스 시 자동 검증합니다. DB 연결은 툴 호출 단위로 생성됩니다 (per-invocation, §1.2).

### 압축 알고리즘

- **100자 미만**: passthrough (압축 없음)
- **100–280자**: 70% 유지
- **280–700자**: 58% 유지
- **700자+**: 42% 유지
- **절약 < 10%**: passthrough

문장 중요도 스코어링: IMPORTANCE_KEYWORDS × 1.5 + thought_type별 특화 키워드 × 1.0 + 위치 보너스 + 길이 가중치

### DB 스키마

SQLite (WAL 모드):
- `sessions` — 세션 메타데이터 및 누적 토큰 절약량
- `nodes` — 추론 노드 (원본 + 압축본 + 상태)
- `edges` — 노드 간 의존 관계
- `ccr_store` — 원본 페이로드 영구 보존, `(hash, session_id)` 복합 PK로 세션 간 독립 보존

## 개발

```bash
# 테스트 실행
uv run pytest

# 특정 테스트 클래스만
uv run pytest tests/test_think.py::TestParentContext -v

# 린트
uv run ruff check src/
```

테스트는 임시 SQLite DB를 사용하며 격리 실행됩니다.

## 변경 이력

> 버전별 전체 이력은 [docs/CHANGELOG.md](docs/CHANGELOG.md),
> 개선 항목(I/Q/R/P/BUG/SEC/PERF/TYPE/TD 시리즈) 색인은 [docs/IMPROVEMENTS.md](docs/IMPROVEMENTS.md),
> 설계 배경·스펙·기술 부채는 [PLAN.md](PLAN.md)를 참조하세요. 아래는 요약입니다.

### v0.43 (2026-06-13) — 현재 버전 · BUG-2 · CLEAN-11 · 138 tests

- **BUG-2** `actions.py` `cleanup_if_needed` import 누락 수정 — TD-12 클린업이 실제로 실행되지 않던 버그 수정
- **CLEAN-11** 스테일 버전 비교 테스트 삭제 (`test_td10_version_matches_document_version`) (139 → 138 tests)

### v0.42 (2026-06-13) — TD-12 · 139 tests

- **TD-12** 세션 만료/최대 수 정책 구현 (`cleanup_if_needed`) — `delete`|`archive` 정책, 현재 세션 보호, 환경 변수 (`DAG_SESSION_MAX_AGE_DAYS`, `DAG_SESSION_MAX_COUNT`, `DAG_CLEANUP_POLICY`) 기반 자동 실행 (130 → 139 tests)

### 이전 버전 요약

| 버전 구간 | 주요 내용 |
|-----------|----------|
| v0.36 ~ v0.40 | TD-9 TypedDict 반환 타입 완비, TD-11 `context_pressure` 토큰 기반 전환(임계값 900/1700, `node_count`→`tokens_original`), `total=False`→`True`+`NotRequired` 정확화, 스테일 주석 정리 |
| v0.35 | Skeleton 재검증 3차 — mcp-builder/Best Practices 신규 위반 0건, M0/M1 중복 통합(130→129 tests), dead init 제거 |
| v0.31 ~ v0.34 | MCP 표준 재리뷰, 테스트 스위트 행위 기준 재구성(459→128 tests), 공급망 감사+SBOM(TD-8), 외부 리뷰 triage·`ccr_hash` 알고리즘 판정 |
| v0.25 ~ v0.30 | MCP 프로토콜 표준 준수 — async+`ToolError`(protocol-level isError), MCP Resource, `action='info'`, 3+1 파일 분리, `prepare_release.py` |
| v0.13 ~ v0.24 | 입력 방어·압축 정확성·MCP 스키마 풍부화 — ToolAnnotations 4종, 전 파라미터 Field 제약, `_split_sentences` false-split 수정 |
| v0.5 ~ v0.12 | ruthless-code-critic 감사 사이클 — 엣지/CCR 버그 수정(R 시리즈), 성능(PERF)·보안(SEC-1)·CJK 안전성 |
| v0.1 ~ v0.4 | 초기 설계 → 단일 툴 통합(v0.2), next_hint 동적화, `context_pressure`·`dag_health` 도입 |
