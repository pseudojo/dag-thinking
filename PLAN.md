# dag-thinking 설계 문서 v0.29

### 버전 변경 내역
| 버전 | 변경 내용 |
|------|----------|
| v0.1 | 초기 설계 — 툴 5개 구조 |
| v0.2 | 툴 1개로 통합, 자동 resolve, 복원 매니페스트 |
| v0.3 | I03 invalidate 존재 검증, I04 created_at 노출, I05 next_hint 동적화 |
| v0.4 | I06 thought_type 키워드 가중치, I07 context_pressure 경보, I08 dag_health 진단 |
| v0.5 | Q-1 session_total_saved 공식 버그 수정, Q-2 edge 배치 조회 분리, Q-3 _validate_think_inputs SRP 추출, Q-4 import 가드 스코프 수정, Q-5 _NEXT_HINTS 직접 접근, Q-6 스테일 주석 제거 |
| v0.6 | R-EDGE 엣지 삭제 방향 버그 수정(parent→child), R-CCR ccr_store 복합 PK + INSERT OR IGNORE, CLEAN-1 _has_cycle() 데드 코드 제거, CLEAN-2 상수 순서 정규화 |
| v0.7 | SEC-1 세션 ID 정보 노출 차단, PERF-1 compress() 트랜잭션 밖 이동, PERF-2 status/restore 읽기 트랜잭션 축소, TYPE-1 타입 어노테이션 완성 |
| v0.8 | I09 context_pressure 트랜잭션 밖 이동, I10 dag_health INVALIDATED 엣지 BFS 제외, I11 _compress_prose 유니코드 문장 구분자 지원 |
| v0.9 | I12 _split_sentences CJK 공백 없는 분리, I13 _is_list_content middle dot 제거, I17 depends_on 길이 상한 검증 |
| v0.10 | I18 estimate_tokens CJK Extension A/Compat/SMP, I21 _join_sentences CJK 재결합, I22 node_name 길이 상한 |
| v0.11 | I20 session_total_saved SELECT 트랜잭션 외부 이동(PERF-2 완성), I23 CJK Compatibility 유니코드 이스케이프, I24 _score_sentence CJK 길이 패널티 제거 |
| v0.12 | I25 _is_cjk_char 헬퍼 추출(CJK 정의 통일), I28 _action_restore LEFT JOIN(N+1 제거), I29 depends_on 중복 제거, I30 session_id 길이 상한 |
| v0.13 | I31 whitespace-only payload 차단, I32 idx_edges_child 인덱스, I33 _split_sentences 줄임표 false-split 수정, I34 edges 루프→executemany+가드 정리 |
| v0.14 | I35 _action_think PERF-2 완성(읽기 쿼리 트랜잭션 외부), I36 note 길이 상한(_MAX_NOTE_LEN=500), I37 _compress_list 최소 k=2 |
| v0.15 | I38 _split_sentences 줄임표+공백 false-split 수정(2-char lookbehind), I39 _compress_prose 최소 k=2, I40 depends_on 빈 경우 cycle check 스킵, I41 _action_invalidate target_node 공백 전용 방어 |
| v0.16 | I42 think 응답 thought_type 필드 추가, I43 status dag.nodes ccr_hash 필드 추가, I44 _is_list_content `+` 불릿 지원(GFM), I45 _compute_dag_health total_nodes 카운트 추가 |
| v0.17 | I46 note=None 방어(None→"" 변환), I47 target_node 공백 정규화(strip), I48 _split_sentences 복합 종결자(?.!/!? 등) 지원 |
| v0.18 | I49 _split_sentences 약어 false-split 방지(Mr./Dr. 등), I50 cycle check 트랜잭션 내부 이동, I51 node_name 공백 정규화(strip), I52 복원 시 삭제 노드 warning, I53 _cascade_invalidate BFS 개선 |
| v0.19 | 중복 테스트 14건 제거 + MCP ToolAnnotations(readOnlyHint/destructiveHint/idempotentHint/openWorldHint) |
| v0.20 | 중복 테스트 제거(IC27/IC28/IC29) + MCP inputSchema Field descriptions(10개 파라미터 전체) |
| v0.21 | 416 tests — 중복 제거(test_i09_i10 T9/T10) + Field 제약(session_id min/maxLength=1/200, note maxLength=500) |
| v0.22 | 415 tests — 중복 제거(test_v12 I28 x2, test_v10 I20 x3) + docstring "Use when:/Don't use when:" 예시 |
| v0.23 | 417 tests — 불필요한 테스트 제거(inspect.getsource 기반 R2-T5/R3-T5) + node_name/reason Field max_length |
| v0.24 | 422 tests — CLAUDE.md/Hook 환경설정 + target_node maxLength=200, payload min/maxLength=80/1500 MCP schema |
| v0.25 | 427 tests — MCP 표준 준수: dag_thinking async+error handling(isError), server name dag_thinking_mcp, _split_sentences null byte(\x00→) |
| v0.26 | 430 tests — MCP Resource(dag-thinking-session://{session_id}), _cascade_invalidate forward_graph 명칭 개선 |
| v0.27 | 431 tests — Skeleton Refactor: version-tracking comment 제거, FastMCP instructions 추가 (MCP discoverability) |
| v0.28 | 437 tests — MCP Best Practices: 3-file split (db.py+actions.py+server.py), action='info' diagnostic (§3.2), XML semantic tags in instructions (§2.2), server.py <500 LOC (§4.2) |
| v0.29 | 443 tests — Post-review fixes: compressor.py 마커 회귀 수정, think.py 추출(actions.py <500 LOC), _action_info 동적 버전(importlib.metadata), session_id min_length 제거, test 미사용 import 제거 |

> **현재 버전**: v0.29 (443 tests) | 최종 갱신: 2026-06-12

---

## 1. 개요 및 설계 배경

### 왜 만드는가
DAG Thinking MCP는 세션이 길어질수록 `resolve_uris` 호출 비용이 누적되는 구조적 문제를 가진다. Headroom의 CCR(Compress-Cache-Retrieve) 패턴은 이를 정확히 해결하지만, 별도 서버로 분리되어 있어 LLM이 "압축 → 추론 → 복원"을 하나의 흐름으로 사용하기 어렵다.

**목표**: 두 개념을 결합해, 구조화된 추론과 컨텍스트 압축이 단일 진입점에서 자연스럽게 동작하는 경량 MCP 서버.

### 핵심 조정 사항 (v0.1 → v0.2)
| 항목 | v0.1 | v0.2 |
|------|------|------|
| 툴 개수 | 5개 (`think`, `resolve`, `retrieve`, `invalidate`, `status`) | **1개** (`dag_thinking(action=...)`) |
| resolve 호출 | 별도 툴 명시 호출 필요 | `think(depends_on=[...])` 시 **자동 내장** |
| 가역성 | ccr_hash 반환만 | **복원 매니페스트** 항상 포함 + 정확한 복원 명령어 |

---

## 2. 설계 원칙

### 원칙 0: 반드시 따라야 하는 원칙
- 개발환경 : 현재 디렉토리를 WSL2에서 진행. uv/uvx/ruff 활용해서 환경 구성. headroom, sequential-thinking mcp 서버 사용.
- Simple is best : 기존에 개발한 dag thinking server와 headroom의 경우 기능은 좋으나 많은 것을 하나에 넣으려 하므로, 가벼운(lightweight) MCP가 필요함.
- 스펙 문서 정의 : 이 PLAN.md가 스펙 역할을 겸한다 (별도 SPEC.md 없음).
- 개발 및 개선작업 과정에서 피드백 루프를 철저하게 지켰는지 확인 필요: `스펙 정의 ➔ 테스트 코드 작성(RED) ➔ 로직 구현(GREEN) ➔ 테스트 수행 ➔ 스펙 부합 여부 확인(ALIGNMENT) ➔ 리팩토링(REFACTOR)` 흐름
- next_hint는 단순 고정 문자열 대신 thought_type별 동적 힌트를 사용한다. 여전히 딕셔너리 조회 수준의 단순 구현을 유지하며, LLM의 다음 행동을 더 구체적으로 안내하는 것이 "Simple is best" 원칙의 실질적 의도에 부합한다.

### 원칙 1: 단일 진입점 (Single Entry Point)
```
이유: LLM이 여러 툴 중 필요한 것을 건너뛰는 문제를 구조적으로 방지.
     선택지가 1개이면 잘못된 선택이 없다.
```
- **MCP 툴은 `dag_thinking` 1개만 노출**
- `action` 파라미터로 동작 분기: `"think"` | `"status"` | `"invalidate"` | `"restore"`

### 원칙 2: 의존 컨텍스트 자동 내장 (Embedded Context)
```
이유: "resolve 먼저 호출하세요" 힌트를 주어도 LLM이 건너뛰는 경우가 발생.
     depends_on 지정 시 응답에 부모 페이로드를 자동으로 포함해 별도 호출 불필요하게 만듦.
```
- `action="think"` + `depends_on=["A","B"]` → 응답 내 `parent_context` 필드에 압축 페이로드 자동 첨부
- 다음 노드 작성 전 이미 부모 컨텍스트가 확보됨

### 원칙 3: 완전한 가역성 (Full Reversibility)
```
이유: 압축 후 복원하려면 session_id와 ccr_hash를 알아야 하는데,
     세션 종료 시점에 LLM이 이를 사용자에게 알려주지 않으면 복원 불가.
```
- `action="status"` 응답 마지막에 항상 **복원 매니페스트** 포함
- 매니페스트 = 복붙 가능한 복원 명령어 목록

### 원칙 4: Live-Zone 준수 (Headroom 상속)
```
현재 작성 중인 노드(active)는 압축하지 않음.
완료(COMPLETED) 노드만 CCR 대상.
```

---

## 3. 단일 툴 인터페이스 명세

### 툴 시그니처

```python
dag_thinking(
    action: Literal["think", "status", "invalidate", "restore"],
    session_id: str,

    # --- action="think" 전용 ---
    node_name: str | None = None,
    thought_type: Literal[
        "Objective","Hypothesis","Assumption",
        "Evidence","Critique","Synthesis","Action"
    ] | None = None,
    payload: str | None = None,          # 80–1500자
    depends_on: list[str] = [],          # 자동 resolve 트리거
    note: str = "",                      # 스크래치패드 (압축 안 함)

    # --- action="invalidate" 전용 ---
    target_node: str | None = None,
    reason: str = "",

    # --- action="restore" 전용 ---
    ccr_hash: str | None = None,         # None이면 세션 전체 목록 반환
) -> dict
```

### action별 동작

#### `action="think"`

```
1. depends_on 각 노드의 COMPLETED 여부 검증
2. 각 부모 노드의 compressed payload + ccr_hash를 응답 내 parent_context에 첨부
3. 사이클 감지 (DFS)
4. payload 압축 (compressor.py)
5. CCR 스토어에 원본 저장
6. 노드 + 엣지 DB 기록

응답:
{
  "status": "created" | "updated",
  "node": "node_name",
  "ccr_hash": "a3f8c2...",
  "parent_context": {                    ← depends_on 있을 때만
    "node_a": {
      "thought_type": "Objective",
      "payload": "...(compressed)...",
      "ccr_hash": "...",
      "is_compressed": true
    }
  },
  "compression": {
    "tokens_saved": 42,
    "session_total_saved": 187
  },
  "next_hint": "<thought_type별 동적 힌트 — 아래 표 참조>",
  "context_pressure": {              ← I07: 세션 컨텍스트 압박 경보
    "level": "low" | "medium" | "high",
    "node_count": 3,
    "hint": "<용량 기반 행동 안내>"
  }
}

context_pressure level 기준:
| level   | 조건                        | 의미 |
|---------|----------------------------|------|
| "low"   | node_count < 8             | 추론 여유 있음 |
| "medium"| 8 ≤ node_count < 15        | Synthesis 검토 권장 |
| "high"  | node_count ≥ 15            | 즉시 수렴 권고 |

next_hint thought_type별 매핑:
| thought_type | next_hint |
|---|---|
| Objective   | "Add Hypothesis or Assumption nodes to explore this objective." |
| Hypothesis  | "Add Evidence or Assumption nodes to support or challenge this hypothesis." |
| Assumption  | "Add Evidence to validate, or Critique to challenge this assumption." |
| Evidence    | "Add Synthesis to draw conclusions, or Critique to challenge the evidence." |
| Critique    | "Add Synthesis to reconcile findings, or revise the critiqued node." |
| Synthesis   | "Add Action nodes to operationalize insights, or call status() to close." |
| Action      | "All conclusions reached. Call status() to review the full DAG." |
```

#### `action="status"`

```
응답:
{
  "session_id": "...",
  "dag": {
    "nodes": [
      {
        "name": "define_problem",
        "thought_type": "Objective",
        "status": "COMPLETED",
        "created_at": "2026-06-08 10:23:45"
      }
    ],
    "edges": [{ "parent": "define_problem", "child": "hypothesis_1" }]
  },
  "metrics": {
    "tokens_original": 820,
    "tokens_compressed": 391,
    "ratio": 0.52
  },
  "restoration_manifest": {              ← 항상 포함
    "how_to_restore": "dag_thinking(action='restore', session_id='<id>', ccr_hash='<hash>')",
    "nodes": [
      {
        "name": "define_problem",
        "type": "Objective",
        "ccr_hash": "a3f8c2d1e5b9f0a2",
        "restore_cmd": "dag_thinking(action='restore', session_id='sess_01', ccr_hash='a3f8c2d1e5b9f0a2')"
      },
      ...
    ]
  },
  "dag_health": {                        ← I08: DAG 수렴 상태 진단
    "is_converging": false,              ← Synthesis/Action COMPLETED 존재 여부
    "max_depth": 2,                      ← 루트에서 최장 추론 체인 깊이 (BFS)
    "orphan_nodes": [],                  ← 엣지 없는 고립 노드 (2+ 노드 세션)
    "thought_type_distribution": {       ← 타입별 노드 수
      "Objective": 1,
      "Hypothesis": 1
    },
    "health_hint": "<상태 기반 행동 안내>"
  }
}
```

#### `action="restore"`

```
ccr_hash 없이 호출:
→ 세션 내 모든 복원 가능 노드 목록 반환
  { "restorable_nodes": [{ name, ccr_hash, restore_cmd }] }

ccr_hash 지정 호출:
→ { "node_name": "...", "original_payload": "...", "tokens": 312 }
```

#### `action="invalidate"`

```
target_node 기준 캐스케이드 무효화 (DFS)

성공 응답:
→ { "invalidated": ["node_a","node_b"], "hint": "Re-create with corrected analysis." }

에러 케이스 (target_node가 세션에 존재하지 않을 때):
→ ValueError: "Node '{target_node}' not found in session '{session_id}'. Use action='status' to see available nodes."
```

#### `action="info"` — §3.2 서버 진단 (MCP Best Practices §3.2)

```
session_id 불필요. 서버 상태 및 설정을 동적으로 반환.

응답:
{
  "server": "dag_thinking_mcp",
  "version": "<pyproject.toml에서 동적 읽기>",   ← importlib.metadata 사용
  "db_path": "<절대 경로>",
  "db_exists": true | false,
  "actions": ["think", "status", "invalidate", "restore", "info"],
  "status": "ready"
}

사용 시점:
- MCP 클라이언트가 서버 버전 검증 시
- DB 경로/존재 여부 진단 시
- 사용 가능한 액션 목록 확인 시
```

---

## 4. 압축 알고리즘 (compressor.py)

```
입력 분기:
  len < 100자           → passthrough (noop)
  list 패턴 감지        → _compress_list()  : 중요도 기반 아이템 샘플링
  else                  → _compress_prose() : 문장 중요도 스코어링

스코어링:
  score = keyword_hits×1.5 + extra_hits×1.0 + position_bonus + length_factor
  IMPORTANCE_KEYWORDS = {error, critical, key, conclusion, therefore,
                         must, result, finding, risk, assumption, ...}
  _TYPE_KEYWORDS[thought_type] = 타입 특화 단어 (I06: ContentRouter 유사 가중치)
    Evidence  → {data, shows, measured, observed, metric, found, test}
    Synthesis → {conclude, summary, overall, combine, integrate, reconcile}
    기타 7개 타입 각각 6-7개 단어 — IMPORTANCE_KEYWORDS와 중복 없음

압축 목표:
  280–700자 → 58% 유지
  700자+    → 42% 유지
  절약 <10% → passthrough (Headroom 규칙)

반환: (compressed_text, ccr_hash_24char, tokens_saved)
```

---

## 5. DB 스키마

```sql
sessions(id TEXT PK, created_at, description, tokens_saved INT DEFAULT 0)

nodes(
  id INT PK AUTOINCREMENT,
  session_id TEXT,
  name TEXT,
  thought_type TEXT,
  payload TEXT,          -- 원본
  compressed TEXT,       -- 압축본 (없으면 NULL)
  ccr_hash TEXT,         -- 24자 hex
  note TEXT,
  status TEXT DEFAULT 'COMPLETED',  -- COMPLETED | INVALIDATED
  created_at DATETIME,
  UNIQUE(session_id, name)
)

edges(session_id, parent, child, PRIMARY KEY(session_id, parent, child))

ccr_store(
  hash TEXT NOT NULL,
  session_id TEXT NOT NULL,
  node_name TEXT,
  original TEXT,         -- 항상 원본 보존
  created_at DATETIME,
  PRIMARY KEY (hash, session_id)  -- 복합 PK: 세션 간 해시 충돌 차단
)
```

---

## 6. 파일 구조 (v0.29 현재)

```
dag-thinking/
├── src/
│   ├── server.py        — FastMCP 얇은 레이어, 단일 툴 정의, MCP Resource   (267 LOC)
│   ├── actions.py       — 비즈니스 로직: status/invalidate/restore/info + dispatcher  (325 LOC)
│   ├── think.py         — think 액션 + 헬퍼: _action_think, _validate_think_inputs,
│   │                      _compute_dag_health, _compute_context_pressure 등          (385 LOC)
│   ├── db.py            — DB 프리미티브: init_db, _db, _ensure_session,
│   │                      _load_forward_edges, _has_cycle_graph, _cascade_invalidate  (155 LOC)
│   ├── compressor.py    — 순수 Python extractive 압축기                               (281 LOC)
│   └── __init__.py      — 빈 패키지 마커
├── tests/
│   └── test_*.py        — pytest 통합 테스트 31개 파일, 443개 테스트
├── pyproject.toml       — 프로젝트 메타데이터, 의존성, ruff 설정
├── PLAN.md              — 스펙 겸 설계 문서 (이 파일)
├── CLAUDE.md            — 개발 가이드 (TDD 원칙, 인코딩 주의사항, 의존성 원칙)
└── .claude/settings.json — PostToolUse hook: ruff 자동 실행
```

**LOC 기준** (MCP Best Practices §4.2 <500 LOC per file):
- 최대 파일: `think.py` 385 LOC ✅ (한도 내, 여유 115 LOC)
- 최소 파일: `db.py` 155 LOC ✅

**의존성**: `fastmcp>=3.3.1`, `pydantic>=2.13.4`, Python ≥ 3.13, 표준 라이브러리만
- ML 라이브러리 (torch, transformers 등) **금지**

---

## 7. 구현 태스크 리스트

```
[ DB / 기반 ]
□ T01. DB 초기화 함수 init_db() — 4개 테이블 자동 생성, WAL 모드
□ T02. _db() 커넥터 헬퍼 — row_factory, busy_timeout=10000
□ T03. _ensure_session() — INSERT OR IGNORE
□ T04. _has_cycle() — DFS 사이클 감지
□ T05. _cascade_invalidate() — 재귀 무효화 + affected 목록 반환

[ compressor.py ]
□ T06. ccr_hash() — sha256 앞 24자
□ T07. estimate_tokens() — len//4
□ T08. _is_list_content() — bullet/numbered 감지
□ T09. _score_sentence() — 키워드 + 위치 + 길이 스코어
□ T10. _compress_list() — 중요도 top-K 아이템 샘플링
□ T11. _compress_prose() — 단락/문장 레벨 extractive
□ T12. compress() — 분기 + passthrough 조건 + (text, hash, saved) 반환

[ server.py — action 구현 ]
□ T13. action="think" 기본 흐름 — 검증 → 사이클 → 압축 → DB 기록 → thought_type별 next_hint 생성
□ T14. action="think" depends_on 자동 resolve — parent_context 첨부
□ T15. action="status" — 토폴로지 + 메트릭 집계 (각 노드에 created_at 포함)
□ T16. action="status" 복원 매니페스트 생성 — restore_cmd 포맷 정확히 일치
□ T17. action="invalidate" 흐름 — target_node 존재 검증 → 미존재 시 ValueError → cascade
□ T18. action="restore" ccr_hash 없음 → 목록 반환
□ T19. action="restore" ccr_hash 있음 → 원본 반환
□ T20. 알 수 없는 action → 명확한 오류 메시지

[ 압축 특화 — I06 ]
□ T28. compressor._TYPE_KEYWORDS — 7개 thought_type별 가중 키워드 dict
□ T28. _score_sentence(extra_keywords) — type-specific 단어 ×1.0 추가 가중
□ T28. compress(text, thought_type) — thought_type으로 extra_keywords 조회 후 전달

[ 컨텍스트 압박 경보 — I07 ]
□ T29. _compute_context_pressure(conn, session_id) → {level, node_count, hint}
□ T29. think 응답에 context_pressure 최상위 키 추가
□ T29. _PRESSURE_MEDIUM=8, _PRESSURE_HIGH=15 상수

[ DAG 수렴 진단 — I08 ]
□ T30. _compute_dag_health(node_rows, edge_rows) → {is_converging, max_depth, orphan_nodes, ...}
□ T30. BFS로 max_depth 계산 (루트 노드에서 출발)
□ T30. status 응답에 dag_health 최상위 키 추가

[ 테스트 ]
□ T21. 기본 think → status → restore 왕복 테스트
□ T22. depends_on + parent_context 자동 첨부 확인
□ T23. 사이클 감지 (A→B→A 시도)
□ T24. 캐스케이드 무효화 (A→B→C에서 A 무효화 시 B,C 포함)
□ T25. restore: hash 없이 목록 / hash 있이 원본 왕복
□ T26. 압축 passthrough 조건 (100자 미만)
□ T27. 압축 후 status 메트릭 tokens_saved 정확성

[ v0.5 품질 개선 — Q 시리즈 ]
□ Q-1. session_total_saved delta 공식 수정: delta = new_tokens_saved − old_tokens_saved
□ Q-2. _load_forward_edges(conn, session_id) → dict[str, list[str]] 분리 (edge 1회 fetch)
□ Q-2. _has_cycle_graph(graph, new_parent, new_child) → bool (DB 접근 없음)
□ Q-2. _action_think cycle loop에서 _load_forward_edges 1회 호출로 교체
□ Q-3. _validate_think_inputs(node_name, thought_type, payload) → None (SRP 추출)
□ Q-3. _action_think 첫 호출을 _validate_think_inputs로 위임
□ Q-4. except ImportError 절 → from src.compressor import (bare 'from compressor' 제거)
□ Q-5. _NEXT_HINTS.get() → _NEXT_HINTS[thought_type] (dead fallback 제거)
□ Q-6. _resolve_parent_context 스테일 주석(YELLOW_3, stub) 제거

[ v0.6 버그 수정 / 구조 정리 — R/CLEAN 시리즈 ]
□ R-EDGE. _action_think upsert: DELETE edges WHERE parent=? → WHERE child=? (outgoing edge 보존)
□ R-CCR.  ccr_store PRIMARY KEY (hash, session_id) 복합키 — 세션 간 해시 충돌 차단
□ R-CCR.  INSERT OR REPLACE → INSERT OR IGNORE (세션 소유권 덮어쓰기 방지)
□ R-CCR.  DELETE FROM ccr_store WHERE hash=old_hash 제거 (content-addressed 원본 보존)
□ CLEAN-1. _has_cycle() 데드 코드 30줄 삭제 (Q-2에서 대체된 이후 호출처 없음)
□ CLEAN-2. 상수(VALID_THOUGHT_TYPES, _PRESSURE_*, _NEXT_HINTS) → 첫 사용 함수 이전으로 이동

[ v0.7 성능·보안·타입 — SEC/PERF/TYPE 시리즈 ]
□ SEC-1.  _action_restore: 타 세션 probe 쿼리 제거 + 에러 메시지 통일 (session_id 노출 방지)
□ PERF-1. _action_think: compress() / estimate_tokens() → DB with conn: 블록 이전으로 이동
□ PERF-2. _action_status / _action_restore: with conn: 범위를 _ensure_session 단독으로 축소
□ TYPE-1. _db() → sqlite3.Connection 반환 타입 어노테이션 추가
□ TYPE-1. _compute_dag_health(node_rows: list[sqlite3.Row], edge_rows: list[sqlite3.Row]) 파라미터 타입 추가

[ v0.8 버그 수정 / 압축 품질 — I09/I10/I11 ]
□ I09. _action_think: _compute_context_pressure() 호출을 with conn: 블록 밖으로 이동
       (PERF-2 원칙 완성 — think에 남아있던 읽기 쿼리를 트랜잭션 외부로)
□ I10. _compute_dag_health: edge 필터링 — parent/child 모두 completed_names에 있는 엣지만 child_map에 포함
       (INVALIDATED 노드 경유 경로가 max_depth / orphan_nodes 계산을 오염하던 버그 수정)
□ I11. compressor.py: _split_sentences(text) 함수 추출 + 유니코드 문장 구분자 지원
       (기존 r"(?<=[.!?])\s+" → r"(?<=[.!?。！？])\s+", 한중일 구두점 추가)

[ v0.9 압축 정확성 / 입력 방어 — I12/I13/I17 ]
□ I12. compressor.py: _split_sentences — CJK 종결자 뒤 공백 없이도 즉시 분리
       (r"(?<=[.!?])\s+|(?<=[。！？])" — ASCII는 공백 필요, CJK는 즉시 분리)
□ I13. compressor.py: _is_list_content — · (U+00B7 middle dot) bullet 인정 제거
       (한국어 단어 구분자/수식 점곱 false positive 차단)
□ I17. server.py: _validate_think_inputs — depends_on 길이 상한 _MAX_DEPENDS_ON=20
       (SQLite IN(?,?,... 999개) 제한 초과 방어)

[ v0.10 압축/토큰/트랜잭션 개선 — I18/I20/I21/I22 ]
□ I18. compressor.py: estimate_tokens — CJK Extension A(U+3400-U+4DBF), Compatibility(U+F900-U+FAFF), Extension B+(ord≥0x20000) 추가
□ I20. server.py: _action_think — session_total_saved SELECT를 with conn: 블록 외부로 이동 (PERF-2 완성)
□ I21. compressor.py: _compress_prose — CJK 종결 문장 재결합 시 공백 없이 결합 (_join_sentences 추출)
□ I22. server.py: _validate_think_inputs — node_name 길이 상한 _MAX_NODE_NAME_LEN=200 추가

[ v0.11 트랜잭션 최적화 / 안전성 / CJK 스코어링 — I20/I23/I24 ]
□ I20. server.py: _action_think — prev_session_total을 with conn: 이전에 SELECT → 트랜잭션 내 SELECT 제거
        with conn: 이전: prev_row = conn.execute("SELECT tokens_saved FROM sessions WHERE id=?", ...).fetchone()
        prev_session_total = prev_row["tokens_saved"] if prev_row else 0
        with conn: 내부: UPDATE sessions (delta) — SELECT 없음
        with conn: 이후: session_total_saved = prev_session_total + delta
□ I23. compressor.py: estimate_tokens — '豈' <= ch <= '﫿' → '豈' <= ch <= '﫿' 유니코드 이스케이프 교체
        (소스 파일 인코딩 훼손 시 리터럴 범위 경계 깨짐 방지)
□ I24. compressor.py: _score_sentence — CJK 텍스트에서 words=[] 일 때 cjk_char_count를 word_count 대리값으로 사용
        words가 비어있으면 len([ch for ch in sentence if ord(ch) > 0x2E7F]) 로 word_count 결정
        (순수 CJK 문장 전체가 word_count=0 → -0.5 패널티 받던 문제 해결)

[ v0.12 DRY / 쿼리 최적화 / 입력 방어 — I25/I28/I29/I30 ]
□ I25. compressor.py: _is_cjk_char(ch) 헬퍼 함수 추출
        estimate_tokens와 _score_sentence 양쪽에서 사용 (CJK 정의 통일, DRY 해소)
        범위: Extension A(U+3400-U+4DBF), Unified(U+4E00-U+9FFF), Compat(U+F900-U+FAFF),
              Hangul(U+AC00-U+D7A3), Hiragana(U+3040-U+309F), Katakana(U+30A0-U+30FF),
              SMP Extension B+(ord>=0x20000)
□ I28. server.py: _action_restore — ccr_store + nodes 별도 2-query를 LEFT JOIN 1-query로 통합
        SELECT c.node_name, c.original, n.status
        FROM ccr_store c LEFT JOIN nodes n ON n.session_id=c.session_id AND n.name=c.node_name
        WHERE c.hash=? AND c.session_id=?
□ I29. server.py: call_dag_thinking — depends_on 중복 항목 순서 보존 제거
        list(dict.fromkeys(depends_on)) 로 중복 제거 후 하위 함수에 전달
□ I30. server.py: call_dag_thinking — session_id 길이 상한 _MAX_SESSION_ID_LEN=200 추가
        node_name과 동일한 200자 제한, blank 검증 직후 실행

[ v0.13 입력 방어 / 인덱스 / 알고리즘 수정 — I31/I32/I33/I34 ]
□ I31. server.py: _validate_think_inputs — 공백 전용 payload 차단
        `if not payload.strip()` 검증 추가 (node_name 공백 검증과 동일 패턴)
        " " * 100 등 의미 없는 페이로드가 80자 최소 길이 검증을 우회하는 버그 수정
□ I32. server.py: init_db() — idx_edges_child 인덱스 추가
        `CREATE INDEX IF NOT EXISTS idx_edges_child ON edges(session_id, child)`
        `DELETE FROM edges WHERE session_id=? AND child=?` (upsert 시 incoming edge 초기화)
        기존 PK(session_id, parent, child) — child 단독 조회 시 풀스캔 발생 수정
□ I33. compressor.py: _split_sentences — 연속 구두점(줄임표 `...`) false-split 수정
        기존: `r"(?<=[.!?])\s+|(?<=[。！？])"`
        변경: `r"(?<=[.!?])(?=[^.!?])\s+|(?<=[。！？])"` — lookahead 추가
        "Wait...really?" → ["Wait", "really?"] 오분리 방지
□ I34. server.py: _action_think — 엣지 삽입 루프 → executemany + 가드 명확화
        기존: `for parent in depends_on: if "error" not in ...: conn.execute(...)`
        변경: 유효 부모 목록 선별 후 `conn.executemany(...)` 1회 호출
        가드 조건: `parent_context.get(p, {}).get("error") is None` (키 유무 vs 빈값 혼동 해소)

[ v0.14 PERF-2 완성 / 입력 방어 / 압축 품질 — I35/I36/I37 ]
□ I35. server.py: _action_think — 읽기 쿼리 트랜잭션 외부 이동 (PERF-2 완성)
        forward_graph, parent_context, prev_row SELECT → with conn: 블록 이전으로 이동
□ I36. server.py: _validate_think_inputs — note 필드 길이 상한 _MAX_NOTE_LEN=500
        비압축 scratchpad 필드의 무제한 입력 방어
□ I37. compressor.py: _compress_list — 최소 k=2 (다중 아이템 과잉 압축 방지)
        `floor_k = min(2, len(lines))`, `k = max(floor_k, round(...))`
        3-item 목록 ratio=0.42: round(1.26)=1 → max(2,1)=2 보존

[ v0.16 응답 풍부화 / 압축 정확성 — I42/I43/I44/I45 ]
□ I42. server.py: _action_think — 응답에 thought_type 필드 추가
        기존: {status, node, ccr_hash, compression, next_hint, context_pressure}
        변경: thought_type 필드 삽입 → LLM이 별도 status() 없이 생성 결과 확인 가능
□ I43. server.py: _action_status — dag.nodes 항목에 ccr_hash 필드 추가
        기존: {name, thought_type, status, created_at}
        변경: ccr_hash 필드 추가 → restoration_manifest 교차 참조 없이 직접 접근
□ I44. compressor.py: _is_list_content — `+` 불릿 프리픽스 지원 (GFM)
        기존: r"^[-*•]\s+"
        변경: r"^[+\-*•]\s+" — GitHub Flavored Markdown `+` 불릿 인정
□ I45. server.py: _compute_dag_health — total_nodes(COMPLETED 노드 수) 추가
        기존 반환 없음 → "total_nodes": len(completed_names) 추가
        빈 세션 경우 total_nodes=0 포함

[ v0.15 압축 정확성 / 성능 / 입력 방어 — I38/I39/I40/I41 ]
□ I38. compressor.py: _split_sentences — 줄임표+공백 false-split 수정 (2-char lookbehind)
        기존: `r"(?<=[.!?])\s+|(?<=[。！？])"`
        변경: `r"(?<=[^.!?][.!?])\s+|(?<=[。！？])"` — 2-char 포지티브 룩비하인드
        "Wait... really?" (공백 있음) → 분리 안 됨 / "Hello. World." → 정상 분리 유지
□ I39. compressor.py: _compress_prose — 최소 k=2 (I37 _compress_list 유사)
        `floor_k = min(2, len(sentences))`, `k = max(floor_k, round(...))`
        2문장 산문 ratio=0.42: round(0.84)=1 → max(2,1)=2 보존
□ I40. server.py: _action_think — depends_on 빈 경우 cycle check 스킵
        `if depends_on:` 가드 추가 — _load_forward_edges DB 조회 불필요 시 생략
□ I41. server.py: _action_invalidate — target_node 공백 전용 방어
        `if not target_node or not target_node.strip()` — node_name 검증과 동일 패턴
```

> **참고**: v0.16-v0.29 세부 태스크는 상단 버전 변경 내역 표 참조.
> 이하는 각 버전의 핵심 구현 항목 요약이다.

```
[ v0.16 응답 풍부화 — I42/I43/I44/I45 ] (완료)
✅ I42. think 응답에 thought_type 필드 추가
✅ I43. status dag.nodes에 ccr_hash 필드 추가
✅ I44. _is_list_content `+` GFM 불릿 지원
✅ I45. _compute_dag_health total_nodes 추가

[ v0.17 입력 방어 보강 — I46/I47/I48 ] (완료)
✅ I46. note=None 방어 (None→"" 변환)
✅ I47. target_node 공백 정규화 (strip)
✅ I48. _split_sentences 복합 종결자 (?.!/!? 등)

[ v0.18 성능·안전성·경고 — I49~I53 ] (완료)
✅ I49. _split_sentences 약어 false-split 방지 (Mr./Dr.)
✅ I50. cycle check 트랜잭션 내부 이동
✅ I51. node_name 공백 정규화 (strip)
✅ I52. restore: 삭제 노드 warning
✅ I53. _cascade_invalidate BFS 개선

[ v0.19 MCP 표준화 ] (완료)
✅ 중복 테스트 14건 제거
✅ ToolAnnotations 추가 (readOnlyHint/destructiveHint/idempotentHint/openWorldHint)

[ v0.20 스키마 풍부화 ] (완료)
✅ 중복 테스트 제거 (IC27/IC28/IC29)
✅ MCP inputSchema Field descriptions 10개 파라미터 전체

[ v0.21-v0.23 제약 강화 ] (완료)
✅ session_id min/maxLength Field 제약
✅ node_name/reason max_length Field 제약
✅ docstring "Use when:/Don't use when:" 예시 추가

[ v0.24 스키마 마무리 ] (완료)
✅ target_node maxLength=200
✅ payload min/maxLength=80/1500
✅ CLAUDE.md/Hook 환경설정

[ v0.25 MCP 프로토콜 표준 준수 ] (완료)
✅ dag_thinking async + isError error handling
✅ server name dag_thinking_mcp
✅ _split_sentences null byte 수정

[ v0.26 MCP Resource ] (완료)
✅ dag-thinking-session://{session_id} Resource 등록
✅ _cascade_invalidate forward_graph 명칭 개선

[ v0.27 Skeleton Refactor ] (완료)
✅ version-tracking comment 제거
✅ FastMCP instructions 추가 (MCP discoverability)

[ v0.28 MCP Best Practices §2.2/§3.2/§4.2 ] (완료)
✅ 3-file split: db.py + actions.py + server.py
✅ action='info' 진단 엔드포인트 (§3.2)
✅ XML semantic tags in instructions (§2.2)
✅ server.py <500 LOC (§4.2)

[ v0.29 Post-review 수정 ] (완료)
✅ think.py 추출 (actions.py 655→325 LOC)
✅ _action_info 동적 버전 (importlib.metadata)
✅ session_id min_length 제거 (info action 호환)
✅ compressor.py 마커 회귀 수정
```

---

## 8. 검증 체크리스트 (구현 완료 후)

```
[ 단일 진입점 ]
□ C01. MCP 툴이 dag_thinking 1개만 노출되는지 확인
□ C02. 잘못된 action 값 입력 시 명확한 오류 (enum 목록 표시) 반환

[ think / 자동 resolve ]
□ C03. depends_on=[] 로 Objective 생성 → parent_context 키 없음(또는 빈 dict)
□ C04. depends_on=["X"] 로 노드 생성 시 응답에 parent_context.X.payload 존재
□ C05. parent_context의 payload가 compressed 버전인지 확인 (원본보다 짧거나 동일)
□ C06. 부모 노드가 INVALIDATED 상태일 때 경고 포함 여부
□ C07. payload 80자 미만 → 오류 반환
□ C08. payload 1500자 초과 → 오류 반환
□ C09. 사이클 시도 → 명확한 오류, 노드 미생성

[ 압축 ]
□ C10. 100자 미만 payload → compressed=NULL, tokens_saved=0
□ C11. 700자 이상 payload → 42% 수준으로 압축 확인 (±10% 허용)
□ C12. 압축 후 ccr_store에 원본 저장 확인 (SELECT 직접 검증)
□ C13. 동일 내용 재입력 시 ccr_hash 동일 여부 (결정론적)

[ 가역성 / 복원 ]
□ C14. status 응답에 항상 restoration_manifest 포함 (노드 0개여도)
□ C15. restore_cmd 문자열이 실제 호출 가능한 형식과 일치
□ C16. restore(ccr_hash=None) → 세션 내 모든 노드 hash 목록 반환
□ C17. restore(ccr_hash="abc") → original_payload가 압축 전 원본과 동일 (byte-level)
□ C18. 다른 session_id로 restore 시도 → 오류 (session scoping)

[ invalidate ]
□ C19. 단일 노드 무효화 → status: INVALIDATED
□ C20. 연쇄 무효화: A→B→C 구조에서 A invalidate → B,C 모두 INVALIDATED
□ C21. INVALIDATED 노드를 동일 이름으로 think() 재생성 → status: COMPLETED로 복귀

[ 메트릭 ]
□ C22. status().metrics.tokens_saved = Σ(각 노드 tokens_saved) 일치
□ C23. compression_ratio = 1 - tokens_compressed / tokens_original 공식 검증

[ invalidate 존재 검증 — I03 ]
□ C24. 존재하지 않는 노드 invalidate 시도 → ValueError 발생, node 이름 포함

[ status created_at — I04 ]
□ C25. status().dag.nodes 각 항목에 created_at 필드 존재 (None 아닌 문자열)

[ next_hint 컨텍스트 — I05 ]
□ C26. Objective 노드 → next_hint에 "Hypothesis" 또는 "Assumption" 포함
□ C27. Hypothesis 노드 → next_hint에 "Evidence" 또는 "Assumption" 포함
□ C28. Assumption 노드 → next_hint에 "Evidence" 또는 "Critique" 포함
□ C29. Evidence 노드 → next_hint에 "Synthesis" 또는 "Critique" 포함
□ C30. Critique 노드 → next_hint에 "Synthesis" 포함
□ C31. Synthesis 노드 → next_hint에 "Action" 또는 "status" 포함
□ C32. Action 노드 → next_hint에 "status()" 포함

[ thought_type 키워드 가중치 — I06 ]
□ C33. _score_sentence(ev_sentence, extra_keywords=_TYPE_KEYWORDS["Evidence"]) > base_score
□ C34. compress(text, "Synthesis") 파라미터 정상 수용, (str, str, int) 반환

[ 컨텍스트 압박 경보 — I07 ]
□ C35. think 응답에 context_pressure.level / .node_count / .hint 필드 존재
□ C36. 첫 번째 노드 → context_pressure.level == "low"
□ C37. _PRESSURE_MEDIUM 이상 노드 → level이 "medium" 또는 "high"

[ DAG 수렴 진단 — I08 ]
□ C38. status 응답에 dag_health.is_converging / .max_depth / .orphan_nodes 필드 존재
□ C39. Synthesis COMPLETED 노드 존재 → is_converging == True
□ C40. A→B→C 체인 → max_depth == 2
□ C41. 연결 없는 2개 노드 → orphan_nodes 비-빈 리스트

[ v0.13 입력 방어 — I31 ]
□ C42. payload 공백 전용(" " * 100) → ValueError 발생
□ C43. payload 정확히 79자 → ValueError (80자 미만 경계값)
□ C44. payload 정확히 80자 → 정상 처리 (경계값 통과)
□ C45. payload 정확히 1500자 → 정상 처리 (상한 경계값 통과)
□ C46. node_name 정확히 200자 → 정상 처리 (상한 경계값 통과)
□ C47. node_name 정확히 201자 → ValueError
□ C48. depends_on 정확히 20개 → 정상 처리 (상한 경계값 통과)
□ C49. depends_on 정확히 21개 → ValueError

[ v0.13 인덱스 / 알고리즘 — I32/I33/I34 ]
□ C50. idx_edges_child 인덱스 존재 확인 (sqlite_master 쿼리)
□ C51. _split_sentences("Wait...really?") → ["Wait...really?"] 또는 2개 이하 분리
        (줄임표가 문장 구분자로 오인 분리되지 않아야 함)
□ C52. _split_sentences("Hello. World.") → ["Hello.", "World."] (정상 분리)
□ C53. depends_on 중복 포함 think() 성공 → 엣지가 정확히 1개만 생성 (I34 executemany)

[ MCP 표준 준수 — v0.25-v0.29 ]
□ C54. FastMCP에 등록된 툴이 dag_thinking 1개만 존재 (list_tools = 1개)
□ C55. action='info' 응답에 server/version/db_path/db_exists/actions/status 필드 포함
□ C56. version 필드 값이 pyproject.toml [project].version과 일치
□ C57. dag-thinking-session://{session_id} Resource 호출 → JSON 세션 상태 반환
□ C58. ValueError 발생 시 `{"isError": True, "error": "..."}` 형식으로 반환
□ C59. src/ 디렉토리 내 print() 호출 없음 (grep 검증 — §3.1 STDIO 경계 준수)
□ C60. ToolAnnotations 4종 (readOnlyHint=False/destructiveHint=True/idempotentHint=False/openWorldHint=False) 확인
```

---

## 9. MCP 표준 준수 현황 (v0.29 기준)

### 9.1 MCP Best Practices & Lessons Learned 체크리스트

| 섹션 | 내용 | 상태 | 비고 |
|------|------|------|------|
| §1.1 단일 툴 설계 | `dag_thinking(action=...)` 1개 | ✅ 완전 준수 | v0.2에서 5개→1개로 통합 |
| §1.2 연결 생명주기 | 툴 호출 당 DB 연결 (per-invocation) | ✅ 완전 준수 | `contextlib.closing(_db(...))` |
| §2.1 스키마/명명 | snake_case, 서버명 `dag_thinking_mcp` | ✅ 완전 준수 | Field 설명+제약 10개 파라미터 전체 |
| §2.2 의미론적 설명 | XML 시맨틱 태그 (`<use_case>`, `<important_notes>`) | ✅ 완전 준수 | FastMCP `instructions=` 파라미터 |
| §2.3 Not-found 부정적 조향 제거 | 노드/해시 미발견 에러 최소화 | ✅ 보안경계 예외 | 노드 존재 확인 = 세션 소유 검증 (보안경계) |
| §3.1 STDIO 경계 통제 | stdout에 `print()` 없음 | ✅ 완전 준수 | 검증: `grep "print(" src/` → 0건 |
| §3.2 info 진단 엔드포인트 | `action='info'` — 동적 버전, DB 상태 반환 | ✅ 완전 준수 | `importlib.metadata.version("dag-thinking")` |
| §4.1 컨테이너 패키징 | Docker 미구성 | ❌ 미준수 | 개발 단계 — 향후 배포 시 필요 |
| §4.2 릴리스 검증 파이프라인 | 자동화 스크립트 없음 | ⚠️ 부분 준수 | LOC <500 ✅, 443 tests ✅, 스크립트 미구성 |

### 9.2 mcp-builder 품질 체크리스트

| 항목 | 상태 | 비고 |
|------|------|------|
| 서버명 `{service}_mcp` 형식 | ✅ | `dag_thinking_mcp` |
| Tool annotations 4종 완비 | ✅ | readOnly/destructive/idempotent/openWorld |
| `async def` 툴 함수 | ✅ | `async def dag_thinking(...)` |
| Field 타입+설명+제약 완비 | ✅ | min/maxLength 전 파라미터 |
| `Use when:/Don't use when:` 예시 | ✅ | 툴 docstring 6개 예시 |
| `isError: True` 에러 패턴 | ✅ | ValueError → `{"isError": True, "error": ...}` |
| stdout 오염 없음 (§3.1) | ✅ | `print()` 0건 확인 |
| Pydantic BaseModel 입력 검증 | ⚠️ | FastMCP의 `Annotated[..., Field()]` 사용 — 유효 패턴 |
| MCP Resource 등록 | ✅ | `dag-thinking-session://{session_id}` (v0.26) |
| 에러 content 형식 MCP 표준 | ⚠️ | `{"error": "..."}` vs `{"content": [{"type":"text",...}]}` — 향후 개선 대상 |

### 9.3 경량성 원칙 (Lightweight)

| 의존성 | 버전 | 역할 |
|--------|------|------|
| `fastmcp` | ≥3.3.1 | MCP 서버 프레임워크 |
| `pydantic` | ≥2.13.4 | Field 제약 및 입력 검증 |
| Python 표준 라이브러리 | 3.13+ | `sqlite3`, `hashlib`, `re`, `collections`, `contextlib`, `importlib.metadata` |
| ML 라이브러리 | ❌ 금지 | `torch`, `transformers` 등 불허 |

---

## 10. 기술 부채 (Tech Debt) — v0.29

**Priority = (영향도 + 위험도) × (6 - 난이도)**  
영향도/위험도/난이도: 1(낮음)~5(높음)

| ID | 항목 | 영향도 | 위험도 | 난이도 | 우선순위 | 비고 |
|----|------|--------|--------|--------|---------|------|
| TD-1 | `test_i11_i12.py` 파일명-스펙 충돌 | 1 | 2 | 1 | 15 | PLAN.md I11/I12와 명칭 혼동 |
| TD-2 | P/R2/R3/STYLE/QUAL/BUG 시리즈 PLAN.md 미등재 | 2 | 2 | 2 | 16 | IMPROVEMENTS.md 신설 필요 |
| TD-3 | `server.py __all__` 내부 심볼 노출 | 2 | 2 | 3 | 12 | 테스트 backward-compat 목적 — 직접 import로 교체 필요 |
| TD-4 | double import fallback `try/except ImportError` | 2 | 1 | 2 | 12 | `actions.py`, `think.py` 양쪽 — 빌드 정상화 후 제거 가능 |
| TD-5 | 에러 응답 형식 불일치 (ValueError→isError) | 3 | 2 | 4 | 10 | MCP 표준 `content[{type,text}]` 형식 — ~50+ 테스트 영향, 대형 변경 |
| TD-6 | Docker 컨테이너 미구성 (§4.1) | 2 | 1 | 4 | 6 | 배포 단계에서 필요 |
| TD-7 | 릴리스 검증 스크립트 미구성 (§4.2) | 2 | 2 | 3 | 12 | `prepare-release.py` 구성 필요 |

### 해소 로드맵

**Phase 1 — 즉시 (현재 사이클):**
- [ ] TD-1. `test_i11_i12.py` 파일명 교정 (명칭 충돌 해소)

**Phase 2 — 다음 사이클:**
- [ ] TD-2. `IMPROVEMENTS.md` 신설 — P/R2/R3/STYLE/QUAL/BUG 시리즈 문서화
- [ ] TD-3. `server.py __all__` 정리 — 테스트가 실제 모듈에서 직접 import
- [ ] TD-4. double import fallback 제거 — 빌드 정상화 후 `.compressor` 단일 경로로

**Phase 3 — 배포 준비 시:**
- [ ] TD-5. `isError` 응답 형식 → MCP 표준 `{"content": [{"type": "text", "text": "..."}]}` 전환 (50+ 테스트 수정)
- [ ] TD-6. Docker 컨테이너 구성 (§4.1 준수)
- [ ] TD-7. `prepare-release.py` 구성 (§4.2 준수)

---

## 11. 구현 요청 프롬프트

> 아래 프롬프트를 Claude에게 전달할 때 **headroom으로 설계 문서를 압축**한 뒤 hash를 함께 전달하고, **sequential-thinking으로 단계별 구현**을 유도합니다.

```
[사전 작업]
1. headroom_compress(content=<설계 문서 전문>)  → hash 확보
2. 아래 프롬프트에 hash 삽입 후 전달

---

아래 설계 문서(hash: {{DESIGN_DOC_HASH}})에 따라 dag-thinking MCP 서버를 구현해 주세요.
설계 문서 원문이 필요하면 headroom_retrieve(hash="{{DESIGN_DOC_HASH}}")로 가져오세요.

## 구현 경로
D:\workspace\request-prompts\dag-thinking\

## 구현 순서 (sequential_think로 각 단계 시작 전 계획 수립)

**Step 1 — compressor.py**
sequential_think로 먼저 구현 계획 수립 후 작성.
- ccr_hash(), estimate_tokens(), _is_list_content()
- _score_sentence(), _compress_list(), _compress_prose()
- compress() → (text, hash, tokens_saved) 반환
- 주요 조건: 280자 미만 passthrough, 절약 <10% passthrough

**Step 2 — server.py (DB + 헬퍼)**
sequential_think로 먼저 구현 계획 수립 후 작성.
- init_db() — sessions, nodes, edges, ccr_store 4개 테이블
- _db(), _ensure_session(), _has_cycle(), _cascade_invalidate()

**Step 3 — server.py (단일 툴 dag_thinking)**
sequential_think로 먼저 구현 계획 수립 후 작성.
- action="think":
  - depends_on → parent_context 자동 내장
  - compress(payload, thought_type) 호출 — I06 thought_type 키워드 가중치 적용
  - compression 응답에 tokens_saved와 session_total_saved 모두 포함
  - next_hint는 thought_type별 동적 문자열 (_NEXT_HINTS 딕셔너리 조회)
  - context_pressure = _compute_context_pressure(conn, session_id) — I07
    → {level: "low"|"medium"|"high", node_count: N, hint: "..."} 응답에 포함
- action="status":
  - restoration_manifest 항상 포함
  - restore_cmd 형식: dag_thinking(action='restore', session_id='...', ccr_hash='...')
  - dag.nodes 각 항목에 created_at 필드 포함
  - dag_health = _compute_dag_health(node_rows, edge_rows) — I08
    → {is_converging, max_depth, orphan_nodes, thought_type_distribution, health_hint} 응답에 포함
- action="restore": hash 없음 → 목록, hash 있음 → 원본
- action="invalidate":
  - target_node DB 존재 여부 먼저 확인
  - 미존재 시 ValueError (메시지에 node 이름과 session_id 포함)
  - 존재 확인 후 cascade

**Step 4 — pyproject.toml**
fastmcp>=3.3.1, pydantic>=2.13.4, Python>=3.13

**Step 5 — tests/test_server.py**
아래 케이스를 pytest로 작성:
- think → status → restore 왕복 (C17 기준 byte-level 동일 확인)
- depends_on 자동 parent_context 첨부 확인
- 사이클 감지 / 캐스케이드 무효화
- restoration_manifest의 restore_cmd 실행 가능 여부

## 절대 규칙
- 툴은 dag_thinking 1개만. resolve/retrieve/status를 별도 툴로 노출하지 말 것.
- action="status" 응답에 restoration_manifest 없으면 구현 오류로 간주.
- ML 라이브러리(torch, transformers 등) 사용 금지.
- 표준 라이브러리 + fastmcp + pydantic만 허용.
```

---

**조정 완료 요약:**
- 툴 5개 → **1개** (`dag_thinking(action=...)`)로 건너뛰기 문제 구조적 차단
- `depends_on` 지정 시 부모 압축 페이로드 **자동 내장** → 별도 resolve 호출 불필요
- `status()` 항상 **복원 매니페스트** 포함 + 복붙 가능한 `restore_cmd` 제공
- `restore(hash=None)` → 전체 목록, `restore(hash=X)` → 원본 반환으로 완전 가역성 보장
- 구현 태스크 27개 + 검증 체크리스트 23개 + 구현 요청 프롬프트 완비
