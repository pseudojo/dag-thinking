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
- **컨텍스트 압박 경보**: 세션 노드 수 기반 `low / medium / high` 경보
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
    action: "think" | "status" | "invalidate" | "restore",
    session_id: str,

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
  "context_pressure": { "level": "low", "node_count": 1, "hint": "..." }
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
| `low` | 노드 < 8개 | 추론 계속 |
| `medium` | 8 ≤ 노드 < 15개 | Synthesis 검토 권장 |
| `high` | 노드 ≥ 15개 | 즉시 수렴 권고 |

## 아키텍처

```
dag-thinking/
├── src/
│   ├── server.py      # FastMCP 서버, 단일 툴, DB 로직
│   └── compressor.py  # 순수 Python extractive 압축기
├── tests/
│   └── test_server.py # pytest 통합 테스트
└── pyproject.toml
```

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
- `ccr_store` — 원본 페이로드 영구 보존 (복원용)

## 개발

```bash
# 테스트 실행
uv run pytest

# 특정 테스트 클래스만
uv run pytest tests/test_server.py::TestThinkStatusRestoreRoundtrip -v

# 린트
uv run ruff check src/
```

테스트는 임시 SQLite DB를 사용하며 격리 실행됩니다.

## 변경 이력

### v0.5 (2026-06-09) — 내부 품질 개선

ruthless-code-critic 감사 기반 TDD 개선 (165 tests · 0 failures):

- **Q-1** `session_total_saved` 공식 버그 수정 — 노드 업데이트 시 `delta = new_saved − old_saved` (기존: `old_compressed` 기준으로 오차 발생)
- **Q-2** edge 배치 조회 분리 — `_load_forward_edges` / `_has_cycle_graph` 신규 함수로 cycle check 루프의 N×DB 쿼리 → 1×DB 쿼리로 개선
- **Q-3** SRP 적용 — `_validate_think_inputs` 독립 함수 추출, `_action_think` 책임 축소
- **Q-4** import 가드 수정 — `from compressor import` → `from src.compressor import` (내부 ImportError 노출 방지)
- **Q-5** dead fallback 제거 — `_NEXT_HINTS.get(thought_type, ...)` → `_NEXT_HINTS[thought_type]`
- **Q-6** 스테일 주석 제거 — 태스크 트래킹 주석(`YELLOW_3`, `stub`) 완전 제거

### v0.4 — I06/I07/I08
- thought_type 키워드 가중치, context_pressure 경보, dag_health 수렴 진단

### v0.3 — I03/I04/I05
- invalidate 존재 검증, created_at 노출, next_hint 동적화

### v0.2 — 통합 설계
- 툴 5개 → 1개, 자동 resolve, 복원 매니페스트
