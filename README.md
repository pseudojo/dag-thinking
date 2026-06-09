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
- `ccr_store` — 원본 페이로드 영구 보존, `(hash, session_id)` 복합 PK로 세션 간 독립 보존

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

### v0.11 (2026-06-10) — 트랜잭션 최적화 / CJK 안전성 / 스코어링 개선

ruthless-code-critic 감사 기반 TDD 개선 (247 tests · 0 failures):

- **I20** `session_total_saved` SELECT 트랜잭션 외부 이동 — PERF-2 원칙 완성. `_action_think`의 `with conn:` 블록 내에서 `UPDATE sessions` 이후 `SELECT tokens_saved`를 실행해 쓰기 락을 불필요하게 연장하던 구조 수정. `prev_session_total`을 `with conn:` 이전에 읽고 `session_total_saved = prev_session_total + delta`로 로컬 계산 교체
- **I23** CJK Compatibility Ideographs 유니코드 이스케이프 교체 — `estimate_tokens()`의 `'豈' <= ch <= '﫿'` 리터럴 문자를 `'豈' <= ch <= '﫿'` 이스케이프로 교체. 소스 파일 인코딩 훼손 시 범위 경계 문자가 깨져 CJK 토큰 계산이 오작동할 위험 제거
- **I24** `_score_sentence()` CJK-aware word_count — `re.findall(r"\b\w+\b")`가 CJK 연속 문자를 하나의 토큰으로 처리해 `word_count=1 < 5` → 전 CJK 문장에 균일 `-0.5` 패널티 부여하던 버그 수정. CJK 문자 비율 > 50% 시 CJK 문자 수를 `word_count` 대리값으로 사용, 짧은/긴 CJK 문장을 정확히 구분

### v0.10 (2026-06-10) — 압축 품질 / 토큰 정확도 / 입력 방어

ruthless-code-critic 감사 기반 TDD 개선 (231 tests · 0 failures):

- **I21** `_join_sentences()` 추출 + `_compress_prose()` CJK 재결합 수정 — v0.9에서 CJK 문장 분리를 추가했으나 재결합은 여전히 `" ".join()` 사용. `"A。B。C。"` 압축 시 `"A。 B。 C。"` (원문에 없는 공백 삽입) 버그 수정. `_CJK_TERMINATORS = frozenset("。！？")`으로 종결자 감지 후 CJK 문장은 공백 없이, ASCII 문장은 공백으로 구분 결합
- **I18** `estimate_tokens()` CJK 확장 범위 보완 — CJK Extension A (U+3400~U+4DBF, ~6,600자), CJK Compatibility Ideographs (U+F900~U+FAFF), CJK Extension B+ SMP (`ord(ch) >= 0x20000`) 미처리 문자들을 `non_cjk`(÷4)로 계산해 토큰 수 최대 8배 과소 산출하던 버그 수정
- **I20** `session_total_saved` 회귀 안전성 — 기존 누적 계산 정확성 검증 테스트 3건 추가
- **I22** `_validate_think_inputs()` `node_name` 길이 상한 — 무제한 길이 `node_name`으로 인한 잠재적 DoS 및 SQL 인덱스 비효율 차단. `_MAX_NODE_NAME_LEN = 200` 상수 도입, blank 검증 직후 길이 검증 실행

### v0.9 (2026-06-10) — 압축 정확성 / 입력 방어

ruthless-code-critic 감사 기반 TDD 개선 (208 tests · 0 failures):

- **I12** `_split_sentences()` CJK 공백 없는 분리 — `r"(?<=[.!?。！？])\s+"` 패턴이 CJK 종결자 뒤 공백을 요구해 `"A。B。"` 형태를 1개 문장으로 처리하던 버그 수정. `r"(?<=[.!?])\s+|(?<=[。！？])"` 로 교정 — ASCII는 공백 필요, CJK는 종결자 자체로 즉시 분리
- **I13** `_is_list_content()` middle dot 오탐 제거 — `·` (U+00B7)이 한국어 단어 구분자나 수학 점곱으로 사용되는 텍스트를 목록으로 오분류하던 문제. bullet 패턴에서 U+00B7 제거, `•` (U+2022)만 허용
- **I17** `_validate_think_inputs()` `depends_on` 길이 상한 — `_resolve_parent_context`의 `IN (?, ...)` 파라미터가 SQLite 제한(999)을 초과할 수 있던 잠재적 `OperationalError`. `_MAX_DEPENDS_ON = 20` 상수 도입, 초과 시 즉시 `ValueError` 발생

### v0.8 (2026-06-10) — 버그 수정 / 압축 품질

ruthless-code-critic 감사 기반 TDD 개선 (194 tests · 0 failures):

- **I09** `_compute_context_pressure()` 쓰기 트랜잭션 밖으로 이동 — `_action_think`의 PERF-2 원칙 완성. `with conn:` 블록 내에 남아있던 COUNT 읽기 쿼리를 커밋 후 실행으로 교정
- **I10** `_compute_dag_health()` INVALIDATED 엣지 BFS 제외 — INVALIDATED 노드와 연결된 엣지가 `max_depth` / `orphan_nodes` 계산을 오염하는 버그 수정. COMPLETED 전용 서브그래프(양쪽 모두 COMPLETED인 엣지)만 사용
- **I11** `_split_sentences()` 함수 추출 + 유니코드 문장 구분자 지원 — `_compress_prose` 내 인라인 분리 로직을 독립 함수로 추출. `r"(?<=[.!?。！？])\s+"` 패턴으로 한중일 구두점(。！？) 지원 추가

### v0.7 (2026-06-09) — 성능 / 보안 / 타입 안전성

ruthless-code-critic 감사 기반 TDD 개선 (181 tests · 0 failures):

- **SEC-1** 세션 ID 정보 노출 차단 — `_action_restore`에서 타 세션 hash 조회 시 다른 세션의 ID를 에러 메시지에 포함하던 probe 쿼리 제거. `"Hash '...' not found in session '...'"` 형태로 통일
- **PERF-1** `compress()` / `estimate_tokens()` DB 쓰기 락 밖으로 이동 — `_action_think`의 SHA-256 + 문장 스코어링 연산이 SQLite 쓰기 락을 불필요하게 점유하던 문제 해결
- **PERF-2** `_action_status` / `_action_restore` 트랜잭션 범위 최소화 — `_ensure_session` 쓰기 1회만 `with conn:` 안에서 실행, 모든 읽기 쿼리를 트랜잭션 밖으로 이동
- **TYPE-1** 타입 어노테이션 완성 — `_db() -> sqlite3.Connection`, `_compute_dag_health(node_rows: list[sqlite3.Row], edge_rows: list[sqlite3.Row])` 파라미터 타입 추가

### v0.6 (2026-06-09) — 버그 수정 / 구조 정리

ruthless-code-critic 감사 기반 TDD 개선 (173 tests · 0 failures):

- **R-EDGE** 엣지 삭제 방향 버그 수정 — 노드 upsert 시 `DELETE WHERE parent=?` → `WHERE child=?`. 기존 코드는 노드를 업데이트할 때 자신의 자식 노드들의 부모 관계를 파괴해 cascade invalidate 경로를 끊는 버그가 있었음
- **R-CCR** `ccr_store` 복합 PK 도입 — `hash TEXT PRIMARY KEY` → `PRIMARY KEY (hash, session_id)`. 두 세션이 동일 내용의 노드를 가질 때 `INSERT OR REPLACE`가 session_id를 덮어써서 한 세션의 restore를 파괴하는 충돌 버그 수정
- **R-CCR** `INSERT OR REPLACE` → `INSERT OR IGNORE` + 고아 DELETE 제거 — 업데이트 시 기존 ccr 원본을 삭제하지 않아 content-addressed 보존 원칙 준수
- **CLEAN-1** `_has_cycle()` 데드 코드 30줄 삭제 — v0.5 Q-2 리팩토링 이후 호출처 없는 함수
- **CLEAN-2** 모듈 상수 순서 정규화 — `VALID_THOUGHT_TYPES`, `_PRESSURE_*`, `_NEXT_HINTS`를 첫 사용 함수 이전으로 이동

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
