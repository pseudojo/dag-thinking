# dag-thinking 설계 문서 v0.39

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
| v0.30 | 459 tests — TD-5 MCP 표준 에러(ToolError → protocol isError), TD-7 prepare_release.py(§4.2 릴리스 검증), TD-4 import fallback 제거, TD-1 테스트 파일명 교정 |
| v0.31 | 459 tests (코드 불변 — 문서 리비전) — mcp-builder/Best Practices 전면 재리뷰: §9 준수 현황 갱신(§4.2 부분 준수로 정정), TD-8/TD-9 신규 등재, TD-2 해소(IMPROVEMENTS.md 전면 갱신), README.md 동기화, §4 압축 100–280자 단계 등재 |
| v0.32 | 128 tests — Skeleton 재구성: 테스트 스위트 행위 기준 8파일 재편(버전 이력 기준 30파일 폐기, 459→128), 테스트를 위한 테스트 삭제, TD-3 해소(`__all__` 재수출 제거), prepare_release `check_ruff` 추가(§4.2-3 정적 분석, 5종 체크) — §12 스펙 참조 |
| v0.33 | 130 tests — TD-8 해소: prepare_release `check_audit`(§4.2-2 공급망 감사 — `uv export --frozen` + `uvx pip-audit`, CycloneDX SBOM) + main 6종 체크. §12.2-1 위반 메타 테스트 재유입 2건 삭제(L5/R4), 소스 스켈레톤 정리(스테일 주석·dead param) — §13 스펙 참조 |
| v0.34 | 130 tests (코드 불변 — 문서 리비전) — 외부 리뷰 4종 triage(§14): TD-11(context_pressure 토큰 기반 전환) 신규·차기 최우선, TD-12(INVALIDATED/ccr_store 보존 정책) 신규, TD-13(압축 인지 효용 측정 — 보류) 신규, TD-9 재평가(9→12), 소프트 가드레일 포지셔닝·sequential-thinking 병행 사용 명문화. §14.4 ccr_hash 알고리즘 판정 — xxHash 제안 기각, stdlib 14종+uuid+Ed25519 전수 실측 후 현행 sha256[:24] 유지(그린필드 재평가 포함, revisit 트리거 명시) |
| v0.35 | 129 tests — Skeleton 재검증 3차(§15): mcp-builder/Best Practices 전면 재대조 신규 위반 0건, §12.2-3 중복 통합(prepare_release M0/M1 → 1건), think.py dead init(delta=0) 제거, 문서 스테일 정정(README test_server.py 경로, §6 LOC 실측) |
| v0.36 | 130 tests — TD-10 해소(pyproject 버전 0.30→0.35 인상 + 버전 검증 테스트), CLEAN-3 해소(_compute_dag_health think.py→actions.py 이전, SRP 준수), TD-9 해소(TypedDict 반환 타입 — ThinkResult/StatusResult/InvalidateResult/RestoreResult/InfoResult 정의) |
| v0.37 | 130 tests — TD-11 해소(context_pressure 노드 수→토큰 기반 전환: SUM(tokens_original), 임계값 900/1700, node_count→tokens_original 반환키 변경, C36/C37 테스트 교체) |
| v0.38 | 131 tests — CLEAN-4 해소(ThinkResult total=False→True + parent_context: NotRequired[dict], 필수/선택 키 타입체커 정확 보장), DOC-2 해소(_validate_think_inputs WHAT 주석 제거) |
| v0.39 | 132 tests — CLEAN-6 해소(RestorePayloadResult total=False→True + warning: NotRequired[str], 3개 필수 키 타입체커 보장), CLEAN-7 해소(compressor.py WHAT 주석 4건 제거·WHY 1건으로 압축) |
| v0.40 | 132 tests (코드 불변 — 주석·문서 정리) — CLEAN-8 해소(compressor.py 스테일 역사 주석·WHAT 인라인 주석 2건 제거), CLEAN-9 해소(actions.py 섹션 헤더 칼러 참조 제거), DOC-3 해소(PLAN.md 문서 제목 v0.37→v0.39 갱신) |

> **현재 버전**: v0.40 (132 tests) | 최종 갱신: 2026-06-13

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
- 개발환경 : Windows 11 네이티브에서 진행 (v0.1 초기 기록은 WSL2 — v0.34 정정). uv/uvx/ruff 활용해서 환경 구성. headroom, sequential-thinking mcp 서버 사용.
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
  100–280자 → 70% 유지 (_RATIO_TINY)
  280–700자 → 58% 유지 (_RATIO_SHORT)
  700자+    → 42% 유지 (_RATIO_LONG)
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

## 6. 파일 구조 (v0.39 현재)

```
dag-thinking/
├── src/
│   ├── server.py        — FastMCP 얇은 레이어, 단일 툴 정의, MCP Resource   (210 LOC)
│   ├── actions.py       — 비즈니스 로직: TypedDicts, status/invalidate/restore/info,
│   │                      _compute_dag_health, dispatcher                            (350 LOC)
│   ├── think.py         — think 액션 + 헬퍼: ThinkResult, _action_think,
│   │                      _validate_think_inputs, _compute_context_pressure 등       (266 LOC)
│   ├── db.py            — DB 프리미티브: init_db, _db, _ensure_session,
│   │                      _load_forward_edges, _has_cycle_graph, _cascade_invalidate  (133 LOC)
│   ├── compressor.py    — 순수 Python extractive 압축기                               (235 LOC)
│   └── __init__.py      — 빈 패키지 마커
├── tests/               — 행위 기준 8개 파일, 132개 테스트 (§12.1 아키텍처)
│   ├── test_compressor.py / test_think.py / test_status.py / test_invalidate.py
│   ├── test_restore.py / test_dispatcher.py / test_mcp_protocol.py
│   ├── test_prepare_release.py
│   └── conftest.py / helpers.py — 공유 픽스처 (src 실제 모듈 직접 import)
├── docs/
│   ├── CHANGELOG.md     — 버전별 변경 이력 전체 (v0.1 ~ 현재, README 요약의 원본)
│   ├── IMPROVEMENTS.md  — 개선 이력 전체 등재 (I/Q/R/P/BUG/STYLE/QUAL/TD 시리즈)
│   └── MCP_Best_Practices_and_Lessons.md — MCP 표준 참조 문서 (mcp-builder 기반)
├── prepare_release.py   — §4.2 릴리스 검증 파이프라인 CLI, 6종 체크 (184 LOC)
├── pyproject.toml       — 프로젝트 메타데이터, 의존성, ruff 설정
├── PLAN.md              — 스펙 겸 설계 문서 (이 파일)
├── README.md            — 사용자 문서 (설치, MCP 설정, 사용법)
├── CLAUDE.md            — 개발 가이드 (TDD 원칙, 인코딩 주의사항, 의존성 원칙)
└── .claude/settings.json — PostToolUse hook: ruff 자동 실행
```

**LOC 기준** (MCP Best Practices §4.2 <500 LOC per file):
- 최대 파일: `think.py` 381 LOC ✅ (한도 내, 여유 119 LOC)
- 최소 파일: `db.py` 153 LOC ✅
- 자동 검증: `prepare_release.py` check_loc_limits() + check_ruff()가 릴리스 시 강제

**의존성**: `fastmcp>=3.3.1`, `pydantic>=2.13.4`, Python ≥ 3.13, 표준 라이브러리만
- ML 라이브러리 (torch, transformers 등) **금지**

---

## 7. 구현 태스크 리스트

```
[ DB / 기반 ]
✅ T01. DB 초기화 함수 init_db() — 4개 테이블 자동 생성, WAL 모드
✅ T02. _db() 커넥터 헬퍼 — row_factory, busy_timeout=10000
✅ T03. _ensure_session() — INSERT OR IGNORE
✅ T04. _has_cycle() — DFS 사이클 감지 (→ v0.6에서 _has_cycle_graph로 대체)
✅ T05. _cascade_invalidate() — BFS 무효화 + affected 목록 반환

[ compressor.py ]
✅ T06. ccr_hash() — sha256 앞 24자
✅ T07. estimate_tokens() — len//4 (CJK 확장 범위 포함, v0.10~v0.11)
✅ T08. _is_list_content() — bullet/numbered 감지 (GFM `+` 포함, v0.16)
✅ T09. _score_sentence() — 키워드 + 위치 + 길이 스코어 (CJK-aware, v0.11)
✅ T10. _compress_list() — 중요도 top-K 아이템 샘플링 (최소 k=2, v0.14)
✅ T11. _compress_prose() — 단락/문장 레벨 extractive (최소 k=2, v0.15)
✅ T12. compress() — 분기 + passthrough 조건 + (text, hash, saved) 반환

[ server.py → think.py/actions.py/server.py 분리 후 기준 (v0.28~v0.29) ]
✅ T13. action="think" 기본 흐름 — 검증 → 사이클 → 압축 → DB 기록 → thought_type별 next_hint 생성
✅ T14. action="think" depends_on 자동 resolve — parent_context 첨부
✅ T15. action="status" — 토폴로지 + 메트릭 집계 (각 노드에 created_at + ccr_hash 포함, v0.16)
✅ T16. action="status" 복원 매니페스트 생성 — restore_cmd 포맷 정확히 일치
✅ T17. action="invalidate" 흐름 — target_node 존재 검증 → 미존재 시 ValueError → cascade
✅ T18. action="restore" ccr_hash 없음 → 목록 반환
✅ T19. action="restore" ccr_hash 있음 → 원본 반환
✅ T20. 알 수 없는 action → 명확한 오류 메시지

[ 압축 특화 — I06 ]
✅ T28. compressor._TYPE_KEYWORDS — 7개 thought_type별 가중 키워드 dict
✅ T28. _score_sentence(extra_keywords) — type-specific 단어 ×1.0 추가 가중
✅ T28. compress(text, thought_type) — thought_type으로 extra_keywords 조회 후 전달

[ 컨텍스트 압박 경보 — I07 ]
✅ T29. _compute_context_pressure(conn, session_id) → {level, node_count, hint}
✅ T29. think 응답에 context_pressure 최상위 키 추가
✅ T29. _PRESSURE_MEDIUM=8, _PRESSURE_HIGH=15 상수

[ DAG 수렴 진단 — I08 ]
✅ T30. _compute_dag_health(node_rows, edge_rows) → {is_converging, max_depth, orphan_nodes, ...}
✅ T30. BFS로 max_depth 계산 (루트 노드에서 출발)
✅ T30. status 응답에 dag_health 최상위 키 추가

[ 테스트 (v0.32 이후 행위 기준 8파일로 재구성) ]
✅ T21. 기본 think → status → restore 왕복 테스트
✅ T22. depends_on + parent_context 자동 첨부 확인
✅ T23. 사이클 감지 (A→B→A 시도)
✅ T24. 캐스케이드 무효화 (A→B→C에서 A 무효화 시 B,C 포함)
✅ T25. restore: hash 없이 목록 / hash 있어 원본 왕복
✅ T26. 압축 passthrough 조건 (100자 미만)
✅ T27. 압축 후 status 메트릭 tokens_saved 정확성

[ v0.5 품질 개선 — Q 시리즈 ]
✅ Q-1. session_total_saved delta 공식 수정: delta = new_tokens_saved − old_tokens_saved
✅ Q-2. _load_forward_edges(conn, session_id) → dict[str, list[str]] 분리 (edge 1회 fetch)
✅ Q-2. _has_cycle_graph(graph, new_parent, new_child) → bool (DB 접근 없음)
✅ Q-2. _action_think cycle loop에서 _load_forward_edges 1회 호출로 교체
✅ Q-3. _validate_think_inputs(node_name, thought_type, payload) → None (SRP 추출)
✅ Q-3. _action_think 첫 호출을 _validate_think_inputs로 위임
✅ Q-4. except ImportError 절 → from src.compressor import (bare 'from compressor' 제거)
✅ Q-5. _NEXT_HINTS.get() → _NEXT_HINTS[thought_type] (dead fallback 제거)
✅ Q-6. _resolve_parent_context 스테일 주석(YELLOW_3, stub) 제거

[ v0.6 버그 수정 / 구조 정리 — R/CLEAN 시리즈 ]
✅ R-EDGE. _action_think upsert: DELETE edges WHERE parent=? → WHERE child=? (outgoing edge 보존)
✅ R-CCR.  ccr_store PRIMARY KEY (hash, session_id) 복합키 — 세션 간 해시 충돌 차단
✅ R-CCR.  INSERT OR REPLACE → INSERT OR IGNORE (세션 소유권 덮어쓰기 방지)
✅ R-CCR.  DELETE FROM ccr_store WHERE hash=old_hash 제거 (content-addressed 원본 보존)
✅ CLEAN-1. _has_cycle() 데드 코드 30줄 삭제 (Q-2에서 대체된 이후 호출처 없음)
✅ CLEAN-2. 상수(VALID_THOUGHT_TYPES, _PRESSURE_*, _NEXT_HINTS) → 첫 사용 함수 이전으로 이동

[ v0.7 성능·보안·타입 — SEC/PERF/TYPE 시리즈 ]
✅ SEC-1.  _action_restore: 타 세션 probe 쿼리 제거 + 에러 메시지 통일 (session_id 노출 방지)
✅ PERF-1. _action_think: compress() / estimate_tokens() → DB with conn: 블록 이전으로 이동
✅ PERF-2. _action_status / _action_restore: with conn: 범위를 _ensure_session 단독으로 축소
✅ TYPE-1. _db() → sqlite3.Connection 반환 타입 어노테이션 추가
✅ TYPE-1. _compute_dag_health(node_rows: list[sqlite3.Row], edge_rows: list[sqlite3.Row]) 파라미터 타입 추가

[ v0.8 버그 수정 / 압축 품질 — I09/I10/I11 ]
✅ I09. _action_think: _compute_context_pressure() 호출을 with conn: 블록 밖으로 이동
       (PERF-2 원칙 완성 — think에 남아있던 읽기 쿼리를 트랜잭션 외부로)
✅ I10. _compute_dag_health: edge 필터링 — parent/child 모두 completed_names에 있는 엣지만 child_map에 포함
       (INVALIDATED 노드 경유 경로가 max_depth / orphan_nodes 계산을 오염하던 버그 수정)
✅ I11. compressor.py: _split_sentences(text) 함수 추출 + 유니코드 문장 구분자 지원
       (기존 r"(?<=[.!?])\s+" → r"(?<=[.!?。！？])\s+", 한중일 구두점 추가)

[ v0.9 압축 정확성 / 입력 방어 — I12/I13/I17 ]
✅ I12. compressor.py: _split_sentences — CJK 종결자 뒤 공백 없이도 즉시 분리
       (r"(?<=[.!?])\s+|(?<=[。！？])" — ASCII는 공백 필요, CJK는 즉시 분리)
✅ I13. compressor.py: _is_list_content — · (U+00B7 middle dot) bullet 인정 제거
       (한국어 단어 구분자/수식 점곱 false positive 차단)
✅ I17. server.py: _validate_think_inputs — depends_on 길이 상한 _MAX_DEPENDS_ON=20
       (SQLite IN(?,?,... 999개) 제한 초과 방어)

[ v0.10 압축/토큰/트랜잭션 개선 — I18/I20/I21/I22 ]
✅ I18. compressor.py: estimate_tokens — CJK Extension A(U+3400-U+4DBF), Compatibility(U+F900-U+FAFF), Extension B+(ord≥0x20000) 추가
✅ I20. server.py: _action_think — session_total_saved SELECT를 with conn: 블록 외부로 이동 (PERF-2 완성)
✅ I21. compressor.py: _compress_prose — CJK 종결 문장 재결합 시 공백 없이 결합 (_join_sentences 추출)
✅ I22. server.py: _validate_think_inputs — node_name 길이 상한 _MAX_NODE_NAME_LEN=200 추가

[ v0.11 트랜잭션 최적화 / 안전성 / CJK 스코어링 — I20/I23/I24 ]
✅ I20. server.py: _action_think — prev_session_total을 with conn: 이전에 SELECT → 트랜잭션 내 SELECT 제거
        with conn: 이전: prev_row = conn.execute("SELECT tokens_saved FROM sessions WHERE id=?", ...).fetchone()
        prev_session_total = prev_row["tokens_saved"] if prev_row else 0
        with conn: 내부: UPDATE sessions (delta) — SELECT 없음
        with conn: 이후: session_total_saved = prev_session_total + delta
✅ I23. compressor.py: estimate_tokens — '豈' <= ch <= '﫿' → '豈' <= ch <= '﫿' 유니코드 이스케이프 교체
        (소스 파일 인코딩 훼손 시 리터럴 범위 경계 깨짐 방지)
✅ I24. compressor.py: _score_sentence — CJK 텍스트에서 words=[] 일 때 cjk_char_count를 word_count 대리값으로 사용
        words가 비어있으면 len([ch for ch in sentence if ord(ch) > 0x2E7F]) 로 word_count 결정
        (순수 CJK 문장 전체가 word_count=0 → -0.5 패널티 받던 문제 해결)

[ v0.12 DRY / 쿼리 최적화 / 입력 방어 — I25/I28/I29/I30 ]
✅ I25. compressor.py: _is_cjk_char(ch) 헬퍼 함수 추출
        estimate_tokens와 _score_sentence 양쪽에서 사용 (CJK 정의 통일, DRY 해소)
        범위: Extension A(U+3400-U+4DBF), Unified(U+4E00-U+9FFF), Compat(U+F900-U+FAFF),
              Hangul(U+AC00-U+D7A3), Hiragana(U+3040-U+309F), Katakana(U+30A0-U+30FF),
              SMP Extension B+(ord>=0x20000)
✅ I28. server.py: _action_restore — ccr_store + nodes 별도 2-query를 LEFT JOIN 1-query로 통합
        SELECT c.node_name, c.original, n.status
        FROM ccr_store c LEFT JOIN nodes n ON n.session_id=c.session_id AND n.name=c.node_name
        WHERE c.hash=? AND c.session_id=?
✅ I29. server.py: call_dag_thinking — depends_on 중복 항목 순서 보존 제거
        list(dict.fromkeys(depends_on)) 로 중복 제거 후 하위 함수에 전달
✅ I30. server.py: call_dag_thinking — session_id 길이 상한 _MAX_SESSION_ID_LEN=200 추가
        node_name과 동일한 200자 제한, blank 검증 직후 실행

[ v0.13 입력 방어 / 인덱스 / 알고리즘 수정 — I31/I32/I33/I34 ]
✅ I31. server.py: _validate_think_inputs — 공백 전용 payload 차단
        `if not payload.strip()` 검증 추가 (node_name 공백 검증과 동일 패턴)
        " " * 100 등 의미 없는 페이로드가 80자 최소 길이 검증을 우회하는 버그 수정
✅ I32. server.py: init_db() — idx_edges_child 인덱스 추가
        `CREATE INDEX IF NOT EXISTS idx_edges_child ON edges(session_id, child)`
        `DELETE FROM edges WHERE session_id=? AND child=?` (upsert 시 incoming edge 초기화)
        기존 PK(session_id, parent, child) — child 단독 조회 시 풀스캔 발생 수정
✅ I33. compressor.py: _split_sentences — 연속 구두점(줄임표 `...`) false-split 수정
        기존: `r"(?<=[.!?])\s+|(?<=[。！？])"`
        변경: `r"(?<=[.!?])(?=[^.!?])\s+|(?<=[。！？])"` — lookahead 추가
        "Wait...really?" → ["Wait", "really?"] 오분리 방지
✅ I34. server.py: _action_think — 엣지 삽입 루프 → executemany + 가드 명확화
        기존: `for parent in depends_on: if "error" not in ...: conn.execute(...)`
        변경: 유효 부모 목록 선별 후 `conn.executemany(...)` 1회 호출
        가드 조건: `parent_context.get(p, {}).get("error") is None` (키 유무 vs 빈값 혼동 해소)

[ v0.14 PERF-2 완성 / 입력 방어 / 압축 품질 — I35/I36/I37 ]
✅ I35. server.py: _action_think — 읽기 쿼리 트랜잭션 외부 이동 (PERF-2 완성)
        forward_graph, parent_context, prev_row SELECT → with conn: 블록 이전으로 이동
✅ I36. server.py: _validate_think_inputs — note 필드 길이 상한 _MAX_NOTE_LEN=500
        비압축 scratchpad 필드의 무제한 입력 방어
✅ I37. compressor.py: _compress_list — 최소 k=2 (다중 아이템 과잉 압축 방지)
        `floor_k = min(2, len(lines))`, `k = max(floor_k, round(...))`
        3-item 목록 ratio=0.42: round(1.26)=1 → max(2,1)=2 보존

[ v0.15 압축 정확성 / 성능 / 입력 방어 — I38/I39/I40/I41 ]
✅ I38. compressor.py: _split_sentences — 줄임표+공백 false-split 수정 (2-char lookbehind)
        기존: `r"(?<=[.!?])\s+|(?<=[。！？])"`
        변경: `r"(?<=[^.!?][.!?])\s+|(?<=[。！？])"` — 2-char 포지티브 룩비하인드
        "Wait... really?" (공백 있음) → 분리 안 됨 / "Hello. World." → 정상 분리 유지
✅ I39. compressor.py: _compress_prose — 최소 k=2 (I37 _compress_list 유사)
        `floor_k = min(2, len(sentences))`, `k = max(floor_k, round(...))`
        2문장 산문 ratio=0.42: round(0.84)=1 → max(2,1)=2 보존
✅ I40. server.py: _action_think — depends_on 빈 경우 cycle check 스킵
        `if depends_on:` 가드 추가 — _load_forward_edges DB 조회 불필요 시 생략
✅ I41. server.py: _action_invalidate — target_node 공백 전용 방어
        `if not target_node or not target_node.strip()` — node_name 검증과 동일 패턴

[ v0.16 응답 풍부화 / 압축 정확성 — I42/I43/I44/I45 ]
✅ I42. server.py: _action_think — 응답에 thought_type 필드 추가
        기존: {status, node, ccr_hash, compression, next_hint, context_pressure}
        변경: thought_type 필드 삽입 → LLM이 별도 status() 없이 생성 결과 확인 가능
✅ I43. server.py: _action_status — dag.nodes 항목에 ccr_hash 필드 추가
        기존: {name, thought_type, status, created_at}
        변경: ccr_hash 필드 추가 → restoration_manifest 교차 참조 없이 직접 접근
✅ I44. compressor.py: _is_list_content — `+` 불릿 프리픽스 지원 (GFM)
        기존: r"^[-*•]\s+"
        변경: r"^[+\-*•]\s+" — GitHub Flavored Markdown `+` 불릿 인정
✅ I45. server.py: _compute_dag_health — total_nodes(COMPLETED 노드 수) 추가
        기존 반환 없음 → "total_nodes": len(completed_names) 추가
        빈 세션 경우 total_nodes=0 포함
```

> **참고**: v0.17-v0.29 세부 태스크는 상단 버전 변경 내역 표 참조.
> 이하는 각 버전의 핵심 구현 항목 요약이다.

```
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

[ v0.30 MCP 표준 에러 + §4.2 릴리스 검증 — TD-5/TD-7/TD-4/TD-1 ] (완료 — 459 tests)

✅ TD-5. server.py: dag_thinking 에러 응답 → MCP protocol-level isError
   문제: 현재 `except ValueError → return {"isError": True, "error": str(e)}` 는
         일반 dict 반환 — MCP 클라이언트는 "성공한 툴 결과"로 인식 (표준 위반).
   해결: `raise ToolError(str(e)) from e` (fastmcp.exceptions.ToolError)
         → FastMCP가 protocol-level isError=True + content[{type:text}] 로 변환.
   시그니처: async def dag_thinking(...) -> dict  (불변 — 에러 경로만 raise로 변경)
   예외 조건: call_dag_thinking이 ValueError를 던지는 모든 입력
             (빈 session_id, 잘못된 thought_type, payload 범위 위반, 미존재 노드 등)
   의사코드:
     BEGIN
       TRY: RETURN call_dag_thinking(action, session_id, ...)
       CATCH ValueError as e: RAISE ToolError(str(e)) FROM e
     END
   영향: tests/test_mcp_v25.py H1 (isError dict 검증) → ToolError raise 검증으로 수정.

✅ TD-7. prepare_release.py (repo 루트) — §4.2 릴리스 검증 파이프라인
   책임: 릴리스 전 검증 체크 4종을 순차 실행하는 단일 CLI 스크립트.
        각 함수는 정확히 하나의 검증만 수행 (SRP).
   의존성: 표준 라이브러리(subprocess/pathlib/sys/asyncio) + fastmcp(기존 의존성) only.
   시그니처:
     def check_loc_limits(src_dir: str, max_loc: int = 500) -> list[str]
        — src_dir 내 *.py 중 총 라인 수 > max_loc 인 파일 경로 목록 (정렬).
          경계: LOC == max_loc → 통과(미포함). 빈 디렉토리 → [].
     def check_git_clean(repo_dir: str) -> tuple[bool, str]
        — git status --porcelain 비면 (True, "working tree clean"),
          더티면 (False, <파일 목록>), git 실패/비-repo → (False, <stderr>).
     def run_tests(repo_dir: str) -> tuple[bool, str]
        — subprocess pytest tests/ -q. 종료코드 0 → (True, 요약 마지막 줄),
          비0 → (False, 출력 끝부분).
     async def smoke_test() -> tuple[bool, str]
        — in-memory Client(mcp)로 list_tools == ["dag_thinking"] 확인 +
          action='info' 호출 is_error=False 확인. 위반 시 (False, 사유).
     def main() -> int — 4종 체크 실행, [PASS]/[FAIL] 출력, 전부 통과 0 / 하나라도 실패 1.
   의사코드(main):
     BEGIN
       results = [check_git_clean(.), check_loc_limits(src), run_tests(.), asyncio.run(smoke_test())]
       FOR (ok, detail) IN results: PRINT "[PASS]" or "[FAIL]" + detail
       RETURN 0 IF all ok ELSE 1
     END
   주: CLI 스크립트는 MCP 서버 프로세스가 아니므로 stdout 출력 허용 (§3.1 비적용).

✅ TD-4. actions.py / think.py: `try: from .compressor ... except ImportError` 폴백 제거
   — 단일 relative import 경로로 정리 (동작 불변, REFACTOR 단계).

✅ TD-1. tests/test_i11_i12.py → tests/test_restore_list_health.py 파일명 교정
   — PLAN.md I11/I12(compressor 문장 분리)와의 명칭 충돌 해소 (동작 불변, REFACTOR 단계).
```

---

## 8. 검증 체크리스트 (구현 완료 후)

> v0.32 행위 기준 8파일 스위트가 전 항목(C01~C66)을 커버 — §12.5 검증 게이트 통과 실측 (현행 129 tests 그린).

```
[ 단일 진입점 ]
✅ C01. MCP 툴이 dag_thinking 1개만 노출되는지 확인
✅ C02. 잘못된 action 값 입력 시 명확한 오류 (enum 목록 표시) 반환

[ think / 자동 resolve ]
✅ C03. depends_on=[] 로 Objective 생성 → parent_context 키 없음(또는 빈 dict)
✅ C04. depends_on=["X"] 로 노드 생성 시 응답에 parent_context.X.payload 존재
✅ C05. parent_context의 payload가 compressed 버전인지 확인 (원본보다 짧거나 동일)
✅ C06. 부모 노드가 INVALIDATED 상태일 때 경고 포함 여부
✅ C07. payload 80자 미만 → 오류 반환
✅ C08. payload 1500자 초과 → 오류 반환
✅ C09. 사이클 시도 → 명확한 오류, 노드 미생성

[ 압축 ]
✅ C10. 100자 미만 payload → compressed=NULL, tokens_saved=0
✅ C11. 700자 이상 payload → 42% 수준으로 압축 확인 (±10% 허용)
✅ C12. 압축 후 ccr_store에 원본 저장 확인 (SELECT 직접 검증)
✅ C13. 동일 내용 재입력 시 ccr_hash 동일 여부 (결정론적)

[ 가역성 / 복원 ]
✅ C14. status 응답에 항상 restoration_manifest 포함 (노드 0개여도)
✅ C15. restore_cmd 문자열이 실제 호출 가능한 형식과 일치
✅ C16. restore(ccr_hash=None) → 세션 내 모든 노드 hash 목록 반환
✅ C17. restore(ccr_hash="abc") → original_payload가 압축 전 원본과 동일 (byte-level)
✅ C18. 다른 session_id로 restore 시도 → 오류 (session scoping)

[ invalidate ]
✅ C19. 단일 노드 무효화 → status: INVALIDATED
✅ C20. 연쇄 무효화: A→B→C 구조에서 A invalidate → B,C 모두 INVALIDATED
✅ C21. INVALIDATED 노드를 동일 이름으로 think() 재생성 → status: COMPLETED로 복귀

[ 메트릭 ]
✅ C22. status().metrics.tokens_saved = Σ(각 노드 tokens_saved) 일치
✅ C23. compression_ratio = 1 - tokens_compressed / tokens_original 공식 검증

[ invalidate 존재 검증 — I03 ]
✅ C24. 존재하지 않는 노드 invalidate 시도 → ValueError 발생, node 이름 포함

[ status created_at — I04 ]
✅ C25. status().dag.nodes 각 항목에 created_at 필드 존재 (None 아닌 문자열)

[ next_hint 컨텍스트 — I05 ]
✅ C26. Objective 노드 → next_hint에 "Hypothesis" 또는 "Assumption" 포함
✅ C27. Hypothesis 노드 → next_hint에 "Evidence" 또는 "Assumption" 포함
✅ C28. Assumption 노드 → next_hint에 "Evidence" 또는 "Critique" 포함
✅ C29. Evidence 노드 → next_hint에 "Synthesis" 또는 "Critique" 포함
✅ C30. Critique 노드 → next_hint에 "Synthesis" 포함
✅ C31. Synthesis 노드 → next_hint에 "Action" 또는 "status" 포함
✅ C32. Action 노드 → next_hint에 "status()" 포함

[ thought_type 키워드 가중치 — I06 ]
✅ C33. _score_sentence(ev_sentence, extra_keywords=_TYPE_KEYWORDS["Evidence"]) > base_score
✅ C34. compress(text, "Synthesis") 파라미터 정상 수용, (str, str, int) 반환

[ 컨텍스트 압박 경보 — I07 ]
✅ C35. think 응답에 context_pressure.level / .node_count / .hint 필드 존재
✅ C36. 첫 번째 노드 → context_pressure.level == "low"
✅ C37. _PRESSURE_MEDIUM 이상 노드 → level이 "medium" 또는 "high"

[ DAG 수렴 진단 — I08 ]
✅ C38. status 응답에 dag_health.is_converging / .max_depth / .orphan_nodes 필드 존재
✅ C39. Synthesis COMPLETED 노드 존재 → is_converging == True
✅ C40. A→B→C 체인 → max_depth == 2
✅ C41. 연결 없는 2개 노드 → orphan_nodes 비-빈 리스트

[ v0.13 입력 방어 — I31 ]
✅ C42. payload 공백 전용(" " * 100) → ValueError 발생
✅ C43. payload 정확히 79자 → ValueError (80자 미만 경계값)
✅ C44. payload 정확히 80자 → 정상 처리 (경계값 통과)
✅ C45. payload 정확히 1500자 → 정상 처리 (상한 경계값 통과)
✅ C46. node_name 정확히 200자 → 정상 처리 (상한 경계값 통과)
✅ C47. node_name 정확히 201자 → ValueError
✅ C48. depends_on 정확히 20개 → 정상 처리 (상한 경계값 통과)
✅ C49. depends_on 정확히 21개 → ValueError

[ v0.13 인덱스 / 알고리즘 — I32/I33/I34 ]
✅ C50. idx_edges_child 인덱스 존재 확인 (sqlite_master 쿼리)
✅ C51. _split_sentences("Wait...really?") → ["Wait...really?"] 또는 2개 이하 분리
        (줄임표가 문장 구분자로 오인 분리되지 않아야 함)
✅ C52. _split_sentences("Hello. World.") → ["Hello.", "World."] (정상 분리)
✅ C53. depends_on 중복 포함 think() 성공 → 엣지가 정확히 1개만 생성 (I34 executemany)

[ MCP 표준 준수 — v0.25-v0.29 ]
✅ C54. FastMCP에 등록된 툴이 dag_thinking 1개만 존재 (list_tools = 1개)
✅ C55. action='info' 응답에 server/version/db_path/db_exists/actions/status 필드 포함
✅ C56. version 필드 값이 pyproject.toml [project].version과 일치
✅ C57. dag-thinking-session://{session_id} Resource 호출 → JSON 세션 상태 반환
✅ C58. ValueError 발생 시 ToolError raise → 클라이언트 측 protocol-level isError=True (v0.30)
✅ C59. src/ 디렉토리 내 print() 호출 없음 (grep 검증 — §3.1 STDIO 경계 준수)
✅ C60. ToolAnnotations 4종 (readOnlyHint=False/destructiveHint=True/idempotentHint=False/openWorldHint=False) 확인

[ v0.30 MCP 표준 에러 / 릴리스 검증 ]
✅ C61. in-memory Client 경유 잘못된 호출 → CallToolResult.is_error == True (protocol-level)
✅ C62. in-memory Client 경유 정상 호출 → is_error == False (회귀 방지)
✅ C63. check_loc_limits: 경계값 — LOC == max_loc 통과, LOC > max_loc 검출
✅ C64. check_git_clean: clean → True / dirty → False(파일명 포함) / 비-git → False
✅ C65. smoke_test: list_tools == ['dag_thinking'] + info 실행 성공
✅ C66. main(): 전부 통과 → exit 0, 하나라도 실패 → exit 1
```

---

## 9. MCP 표준 준수 현황 (v0.33 기준 — v0.35 재대조 확인)

> v0.33 재리뷰 (2026-06-12): mcp-builder 스킬 + MCP Best Practices 문서 전면 대조.
> 검증 실측 — 130 tests 통과, `grep "print(" src/` 0건, 전 소스 파일 <500 LOC,
> `prepare_release.py` 6종 체크 전부 PASS (pip-audit 실측: 공급망 68 컴포넌트 무취약점).
> 리뷰 기준 문서 CCR 캐시: `headroom_retrieve(hash="ff35609c3729d407b6b6b5ac")`
> v0.35 재대조 (2026-06-13): 신규 표준 위반 0건 — 현황표 변동 없음 (§15.1, 129 tests 그린).

### 9.1 MCP Best Practices & Lessons Learned 체크리스트

| 섹션 | 내용 | 상태 | 비고 |
|------|------|------|------|
| §1.1 단일 툴 설계 | `dag_thinking(action=...)` 1개 | ✅ 완전 준수 | v0.2에서 5개→1개로 통합 |
| §1.2 연결 생명주기 | 툴 호출 당 DB 연결 (per-invocation) | ✅ 완전 준수 | `contextlib.closing(_db(...))` |
| §2.1 스키마/명명 | snake_case, 서버명 `dag_thinking_mcp` | ✅ 완전 준수 | 엄격 스키마 + 관대한 파싱 (strip/dedup) |
| §2.2 의미론적 설명 | XML 시맨틱 태그 (`<use_case>`, `<important_notes>`) | ✅ 완전 준수 | FastMCP `instructions=` 파라미터 |
| §2.3 Not-found 부정적 조향 제거 | 노드/해시 미발견 에러 최소화 | ✅ 보안경계 예외 | 노드 존재 확인 = 세션 소유 검증 (보안경계) |
| §3.1 STDIO 경계 통제 | stdout에 `print()` 없음 | ✅ 완전 준수 | 검증: `grep "print(" src/` → 0건 |
| §3.2 info 진단 엔드포인트 | `action='info'` — 동적 버전, DB 상태 반환 | ✅ 완전 준수 | `importlib.metadata.version("dag-thinking")` |
| §4.1 컨테이너 패키징 | Docker 미구성 | ❌ 미준수 | 개발 단계 — 향후 배포 시 필요 (TD-6) |
| §4.2 릴리스 검증 파이프라인 | `prepare_release.py` — git/LOC/ruff/audit/tests/smoke 6종 | ✅ 준수 | v0.33 공급망 감사+CycloneDX SBOM 추가(§4.2-2, TD-8 해소). origin sync는 의도적 미적용 (§13.4) |

### 9.2 mcp-builder 품질 체크리스트

| 항목 | 상태 | 비고 |
|------|------|------|
| 서버명 `{service}_mcp` 형식 | ✅ | `dag_thinking_mcp` |
| Tool annotations 4종 완비 | ✅ | readOnly/destructive/idempotent/openWorld |
| `async def` 툴 함수 | ✅ | `async def dag_thinking(...)` |
| Field 타입+설명+제약 완비 | ✅ | min/maxLength 전 파라미터 |
| `Use when:/Don't use when:` 예시 | ✅ | 툴 docstring 6개 예시 |
| protocol-level isError 에러 패턴 | ✅ | ValueError → `raise ToolError` → FastMCP가 isError=True + content 변환 (v0.30) |
| stdout 오염 없음 (§3.1) | ✅ | `print()` 0건 확인 |
| Pydantic BaseModel 입력 검증 | ⚠️ | FastMCP의 `Annotated[..., Field()]` 사용 — 유효 패턴 |
| MCP Resource 등록 | ✅ | `dag-thinking-session://{session_id}` (v0.26) |
| 에러 content 형식 MCP 표준 | ✅ | ToolError → `content[{type:text}]` + isError=True (v0.30 TD-5 해소) |
| outputSchema / 구조화 출력 모델 | ✅ | TypedDict 반환 타입 정의 완료 — ThinkResult/StatusResult/InvalidateResult/RestoreResult/InfoResult (v0.36 TD-9 해소) |

### 9.3 의도적 미적용 (Intentional Deviations)

mcp-builder 체크리스트 중 아래 항목은 검토 후 **의도적으로 적용하지 않음**. 부채가 아니라 설계 결정이다.

| 항목 | mcp-builder 권고 | 미적용 근거 |
|------|------|------|
| `response_format` (markdown/json) | 데이터 반환 툴은 양식 선택 지원 | 소비자가 LLM 단일 — 구조화 dict가 곧 응답. `next_hint`/`restoration_manifest` 등 필드 단위 소비라 markdown 변환은 정보 손실만 발생 |
| 페이지네이션 (`limit`/`offset`) | 목록 반환 툴은 페이지네이션 필수 | 세션 노드 수가 `context_pressure`(≥15 = high, 즉시 수렴 권고)로 구조적으로 상한 — 단일 세션이 수백 노드에 도달하지 않는 설계 |
| Lifespan 영속 연결 | 서버 수명 주기 리소스 관리 | Best Practices §1.2와 정면 충돌 — per-invocation 연결이 우선 (degraded state에서도 서버 기동 보장) |
| Context 주입 (progress/elicit) | 장기 작업 진행률 보고 | 모든 액션이 ms 단위 로컬 SQLite 연산 — 진행률 보고 무의미 |

### 9.4 경량성 원칙 (Lightweight)

| 의존성 | 버전 | 역할 |
|--------|------|------|
| `fastmcp` | ≥3.3.1 | MCP 서버 프레임워크 |
| `pydantic` | ≥2.13.4 | Field 제약 및 입력 검증 |
| Python 표준 라이브러리 | 3.13+ | `sqlite3`, `hashlib`, `re`, `collections`, `contextlib`, `importlib.metadata` |
| ML 라이브러리 | ❌ 금지 | `torch`, `transformers` 등 불허 |

---

## 10. 기술 부채 (Tech Debt) — v0.34

**Priority = (영향도 + 위험도) × (6 - 난이도)**  
영향도/위험도/난이도: 1(낮음)~5(높음)

| ID | 항목 | 분류 | 영향도 | 위험도 | 난이도 | 우선순위 | 비고 |
|----|------|------|--------|--------|--------|---------|------|
| ~~TD-1~~ | ~~`test_i11_i12.py` 파일명-스펙 충돌~~ | 문서 | — | — | — | 해소 | v0.30: `test_restore_list_health.py`로 rename |
| ~~TD-2~~ | ~~P/R/STYLE/QUAL/BUG 시리즈 미등재~~ | 문서 | — | — | — | 해소 | v0.31: IMPROVEMENTS.md 전면 갱신 (v0.13~v0.30 + 전 시리즈 등재) |
| ~~TD-3~~ | ~~`server.py __all__` 내부 심볼 노출~~ | 코드 | — | — | — | 해소 | v0.32: `__all__` 재수출 제거, 테스트가 실제 모듈에서 직접 import |
| ~~TD-4~~ | ~~double import fallback~~ | 코드 | — | — | — | 해소 | v0.30: `.compressor` 단일 relative import |
| ~~TD-5~~ | ~~에러 응답 형식 불일치~~ | 코드 | — | — | — | 해소 | v0.30: `raise ToolError` — 실측 영향 테스트 3건(50+ 추정은 과대) |
| TD-6 | Docker 컨테이너 미구성 (§4.1) | 인프라 | 2 | 1 | 4 | 6 | 배포 단계에서 필요 |
| ~~TD-7~~ | ~~릴리스 검증 스크립트 미구성~~ | 인프라 | — | — | — | 해소 | v0.30: `prepare_release.py` — git/LOC/tests/smoke 4종 |
| ~~TD-8~~ | ~~prepare_release.py 공급망 검증 누락 (§4.2-2)~~ | 의존성 | — | — | — | 해소 | v0.33: `check_audit` — `uvx pip-audit` 격리 실행(프로젝트 의존성 불변) + CycloneDX SBOM. dev 그룹 추가 불필요로 판명 |
| ~~TD-9~~ | ~~툴 반환 outputSchema 미정의~~ | 코드 | — | — | — | 해소 | v0.36: ThinkResult/StatusResult/InvalidateResult/RestoreListResult/RestorePayloadResult/InfoResult TypedDict 정의 완료 |
| ~~TD-10~~ | ~~패키지 버전 인상 대기~~ | 문서 | — | — | — | 해소 | v0.36: pyproject.toml 0.30→0.35 인상 + 버전 검증 테스트 추가 |
| ~~CLEAN-3~~ | ~~_compute_dag_health SRP 위반 (think.py 정의, actions.py 사용)~~ | 코드 | — | — | — | 해소 | v0.36: think.py→actions.py 이전 |
| ~~TD-11~~ | ~~context_pressure 노드 수 기반 — 토큰 기반 전환~~ | 코드 | — | — | — | 해소 | v0.37: `SUM(tokens_original)`, `_PRESSURE_MEDIUM_TOKENS=900`/`_PRESSURE_HIGH_TOKENS=1700`, 반환키 `node_count→tokens_original`, C36/C37 테스트 교체 |
| ~~CLEAN-4~~ | ~~ThinkResult(total=False) — 모든 키 Optional, 7개 필수 키 타입 불안전~~ | 코드 | — | — | — | 해소 | v0.38: `total=True`(기본) + `parent_context: NotRequired[dict]`, 필수/선택 TypedDict 메타검증 테스트 추가 |
| ~~DOC-2~~ | ~~_validate_think_inputs WHAT 주석 (CLAUDE.md 주석 원칙 위반)~~ | 문서 | — | — | — | 해소 | v0.38: 주석 제거 |
| ~~CLEAN-6~~ | ~~RestorePayloadResult(total=False) — 3개 필수 키 타입 불안전~~ | 코드 | — | — | — | 해소 | v0.39: `total=True` + `warning: NotRequired[str]`, 타입 메타검증 테스트 추가 |
| ~~CLEAN-7~~ | ~~compressor.py WHAT 주석 4건 (CLAUDE.md 위반)~~ | 문서 | — | — | — | 해소 | v0.39: 4건 제거, CJK word-count 이슈 WHY 1줄로 압축 |
| ~~CLEAN-8~~ | ~~compressor.py 스테일 역사 주석·WHAT 인라인 주석 2건~~ | 문서 | — | — | — | 해소 | v0.40: `ContentRouter 유사` 역사 주석·`_SAVINGS_THRESHOLD` WHAT 주석 제거 |
| ~~CLEAN-9~~ | ~~actions.py 섹션 헤더 칼러 참조 (CLAUDE.md 위반)~~ | 문서 | — | — | — | 해소 | v0.40: `(moved from think.py — used only by _action_status)` 제거 |
| ~~DOC-3~~ | ~~PLAN.md 문서 제목 v0.37 스테일~~ | 문서 | — | — | — | 해소 | v0.40: 제목 v0.39로 갱신 |
| TD-12 | INVALIDATED/ccr_store 보존 정책 부재 (§14.1) | 코드 | 1 | 2 | 3 | 9 | 가역성 vs 스토리지 트레이드오프(의도적 content-addressed 보존). 세션 아카이브 / 도달불가 hash 프루닝 / 세션별 quota 중 택일. nodes는 UNIQUE upsert·payload ≤1500자·세션 구조적 상한으로 현재 실위험 낮음 |
| TD-13 | 압축 인지 효용(cognitive effect) 측정 부재 (§14.1) | 설계 | 2 | 2 | 5 | 4 | 압축된 parent_context로 원문 동등 품질 추론이 가능한지 미실증. 정량 평가는 LLM-judge 필요 — 경량 원칙과 충돌로 보류. byte-identical restore(C17)가 위험 완화: 압축본은 힌트, 원본은 ccr_store 보존 |

### 해소 로드맵

**Phase 2 — 다음 사이클:** (완료 — Phase 2 항목 소진)

**Phase 3 — 배포 준비 시:**
- [ ] TD-6. Docker 컨테이너 구성 (§4.1 준수)
- [ ] TD-12. 세션 보존/프루닝 정책 (장기 운영 데이터 확보 후)

**보류:** TD-13 (LLM-judge 기반 압축 효용 평가 — 경량 원칙과 충돌, 가역성으로 완화됨)

**해소 완료:** TD-1(v0.30 파일명), TD-2(v0.31 IMPROVEMENTS.md), TD-3(v0.32 `__all__` 제거), TD-4(v0.30 import fallback), TD-5(v0.30 ToolError), TD-7(v0.30 prepare_release.py), TD-8(v0.33 check_audit), TD-9(v0.36 TypedDict), TD-10(v0.36 버전 인상), CLEAN-3(v0.36 SRP 이전), TD-11(v0.37 토큰 기반 전환), CLEAN-4(v0.38 ThinkResult 키 강화), DOC-2(v0.38 WHAT 주석 제거), CLEAN-6(v0.39 RestorePayloadResult 키 강화), CLEAN-7(v0.39 compressor.py WHAT 주석), CLEAN-8(v0.40 스테일 역사·인라인), CLEAN-9(v0.40 칼러 참조), DOC-3(v0.40 문서 제목)

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
- 주요 조건: 100자 미만 passthrough, 절약 <10% passthrough

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

**Step 5 — tests/ (행위 기준 8파일)**
아래 케이스를 pytest로 작성 (v0.32 이후 파일 구조):
- `test_think.py`: think → status → restore 왕복 (C17 기준 byte-level 동일 확인)
- `test_think.py`: depends_on 자동 parent_context 첨부 확인
- `test_think.py`: 사이클 감지 / `test_invalidate.py`: 캐스케이드 무효화
- `test_status.py`: restoration_manifest의 restore_cmd 실행 가능 여부

## 절대 규칙
- 툴은 dag_thinking 1개만. resolve/retrieve/status를 별도 툴로 노출하지 말 것.
- action="status" 응답에 restoration_manifest 없으면 구현 오류로 간주.
- ML 라이브러리(torch, transformers 등) 사용 금지.
- 표준 라이브러리 + fastmcp + pydantic만 허용.
```

---

## 12. v0.32 Skeleton 재구성 스펙

### 12.1 목적 및 책임 (SRP)

**목적**: 26회 증분 패치로 파편화된 테스트 스위트를 핵심 행위(behavior) 골격만 남기고 재구성한다.
소스 5-모듈 구조는 유지하되 테스트 backward-compat 전용 재수출(`__all__`)을 제거한다(TD-3).

**책임 분리**: 각 테스트 파일은 정확히 하나의 공개 인터페이스 영역만 검증한다.

| 파일 | 검증 대상 (공개 인터페이스) |
|------|------|
| `tests/test_compressor.py` | `compress()` / `estimate_tokens()` / `ccr_hash()` + 문장 분리 핵심 회귀 |
| `tests/test_think.py` | `call_dag_thinking(action='think')` — 검증·사이클·parent_context·압박 경보 |
| `tests/test_status.py` | `call_dag_thinking(action='status')` — 토폴로지·메트릭·매니페스트·dag_health |
| `tests/test_invalidate.py` | `call_dag_thinking(action='invalidate')` — 캐스케이드·존재 검증·재생성 |
| `tests/test_restore.py` | `call_dag_thinking(action='restore')` — 목록·원본 왕복·세션 격리·경고 |
| `tests/test_dispatcher.py` | 액션 라우팅·session_id 검증·`action='info'` |
| `tests/test_mcp_protocol.py` | FastMCP 레이어 — in-memory Client, 스키마, annotations, Resource, ToolError |
| `tests/test_prepare_release.py` | 릴리스 파이프라인 (기존 유지 + check_ruff) |

### 12.2 테스트 삭제 기준 (테스트를 위한 테스트)

아래 4종은 행위 검증이 아니므로 삭제한다:

1. **메타 테스트**: 테스트 스위트가 lint/스타일을 subprocess로 검사 (`uv run ruff` in test) —
   §4.2-3 정적 분석은 릴리스 파이프라인(`prepare_release.check_ruff`)의 책임
2. **구현 세부 테스트**: private 함수 rename/인라인에 깨지는 테스트, SQL 인덱스 존재 검사
   (`sqlite_master` 쿼리), 변수명 리네임 안전망 — 공개 API 행위로 커버되면 삭제
3. **중복 테스트**: 동일 행위를 버전별 파일에서 재검증 (v05~v18, mcp_v25~v30 파편화)
4. **백워드-컴팻 테스트**: `src.server` 재수출 경유 import에 의존하는 테스트 —
   실제 정의 모듈에서 직접 import로 재작성

**유지 예외**: `_split_sentences`는 private이지만 4건의 실버그(I33/I38/I48/I49) 회귀 가드로
최소 테스트 유지 — `compress()` 경유로는 문장 경계 정확성을 결정론적으로 관찰 불가.

### 12.3 신규 코드: prepare_release.check_ruff (§4.2-3)

```
시그니처: def check_ruff(src_dir: str) -> tuple[bool, str]

의사코드:
  BEGIN
    TRY: result = subprocess.run(["uv","run","--no-sync","ruff","check",src_dir],
                                 capture_output, text, timeout=120)
    CATCH OSError|TimeoutExpired as e: RETURN (False, f"ruff execution failed: {e}")
    IF result.returncode == 0: RETURN (True, "no lint violations")
    RETURN (False, stdout 마지막 20줄 or stderr)
  END

제약: --no-sync 필수 — uv sync가 잠긴 dag-thinking.exe 재설치를 시도하지 않도록 차단.
경계: src_dir 미존재 → ruff가 비0 종료 → (False, ...) 경로로 자연 처리.
main(): 5종 체크로 확장 — [source control, LOC, ruff, tests, smoke]
```

### 12.4 소스 변경 (REFACTOR — 동작 불변)

- `server.py`: `__all__` 및 backward-compat 재수출 import 제거 — 실사용 심볼만 import
- `actions.py`: `__all__` 제거, think.py 재수출 정리 — dispatcher 실사용 심볼만 import
- `tests/conftest.py`/`helpers.py`: `src.db.init_db`, `src.actions.call_dag_thinking` 직접 import

### 12.5 검증 게이트

- 신규 스위트가 §8 검증 체크리스트(C01~C66) 전 항목을 커버할 것
- 구 스위트 삭제 후 전체 그린 + `prepare_release.py` 5종 체크 통과
- 소스/테스트 파일 모두 <500 LOC 유지

### 12.6 완료 결과 (2026-06-12)

| 항목 | Before | After |
|------|--------|-------|
| 테스트 파일 | 31개 (버전 이력 기준) | 8개 (행위 기준) |
| 테스트 수 | 459 | 128 |
| `server.py` LOC | 269 (`__all__` 17개 재수출) | 233 (재수출 0) |
| `actions.py` LOC | 321 (`__all__` 19개 재수출) | 287 (재수출 0) |
| prepare_release 체크 | 4종 | 5종 (+ check_ruff §4.2-3) |
| ruff 강제 지점 | 테스트 스위트 내 subprocess (메타 테스트) | 릴리스 파이프라인 + PostToolUse hook |

삭제된 테스트 분류: 중복(버전별 재검증) 다수, 메타 테스트(ruff subprocess, LOC 검사),
구현 세부(SQL 인덱스 존재, 변수명 리네임 가드, inspect 기반), 백워드-컴팻(`src.server` 재수출 경유).
유지 예외: `_split_sentences` 회귀 가드 6건 (I33/I38/I48/I49/I12/H3 실버그 — §12.2 근거).

---

## 13. v0.33 스펙 — §4.2-2 공급망 검증(TD-8) + 메타 테스트 정리

### 13.1 배경 (mcp-builder + Best Practices 재리뷰, 2026-06-12)

리뷰 기준: mcp-builder 스킬 체크리스트 + MCP Best Practices 문서
(CCR 캐시: `headroom_retrieve(hash="ff35609c3729d407b6b6b5ac")` — 구 해시 만료로 재압축).

판정: §1~§3 전 항목 준수 유지 (§9 현황표와 동일). 실행 가능한 잔여 격차는
§4.2-2 공급망 검증(TD-8) 하나이며, 테스트 스위트에 §12.2-1 위반 메타 테스트 2건이 재유입됨.

### 13.2 테스트 삭제 (§12.2 기준 적용 — 테스트를 위한 테스트)

| 대상 | 근거 |
|------|------|
| `test_prepare_release.py::test_l5_real_src_dir_within_limit` | §12.2-1 메타 테스트 — 실제 `src/` LOC 검사를 테스트 스위트에서 수행. 릴리스 파이프라인(`check_loc_limits` 실행) 책임 중복 |
| `test_prepare_release.py::test_r4_real_src_is_clean` | §12.2-1 메타 테스트 — 테스트 스위트 내 ruff subprocess 실행. v0.32에서 삭제한 패턴의 재유입. ruff 강제는 릴리스 파이프라인 + PostToolUse hook 책임 |

주: L1~L4/R1~R3(tmp 디렉토리·mock 기반 행위 테스트)와 S1(`smoke_test` 유일 happy-path 커버)은 유지.

### 13.3 소스 스켈레톤 정리 (REFACTOR — 동작 불변)

- `think.py`: "Constants (shared with actions.py via re-export)" 주석 — TD-3 해소(v0.32)로 스테일. 제거.
- `db.py`: `_cascade_invalidate(edges_graph=None)` — 호출처 없는 dead parameter (YAGNI). 제거.
- `think.py`: `_compute_dag_health` 반환 dict의 `len(completed_names)` → 기 계산된 `total_nodes` 변수 재사용.

### 13.4 신규 코드: prepare_release.check_audit (§4.2-2, TD-8)

**책임**: 공급망 취약점 감사 + SBOM 생성 — 정확히 하나의 검증 (SRP).
**의존성**: 표준 라이브러리(`subprocess`/`tempfile`/`os`) only. pip-audit는 `uvx` 격리 실행 —
프로젝트 의존성/pyproject.toml 불변 (Lightweight 원칙 + exe-lock 제약 준수).

```
시그니처: def check_audit(repo_dir: str, sbom_path: str = "sbom.json") -> tuple[bool, str]

입력 제약:
  repo_dir: uv.lock이 존재하는 프로젝트 루트. 미존재/비-프로젝트 → uv export 비0 종료 → (False, ...) 자연 처리.
  sbom_path: SBOM 출력 경로 (repo_dir 상대). .gitignore 등재 필수 —
             다음 릴리스 런의 check_git_clean 오염 방지.

의사코드:
  BEGIN
    fd, req_path = tempfile.mkstemp(suffix=".txt"); os.close(fd)  # Windows 파일 잠금 회피
    TRY:
      export = subprocess.run(["uv","export","--frozen","--no-dev","--no-emit-project",
                               "--format","requirements-txt","-o",req_path],
                              cwd=repo_dir, capture_output, text, timeout=120)
      IF export.returncode != 0: RETURN (False, export.stderr tail)
      audit = subprocess.run(["uvx","pip-audit","-r",req_path,"--no-deps",
                              "-f","cyclonedx-json","-o",sbom_path],
                             cwd=repo_dir, capture_output, text, timeout=300)
      IF audit.returncode == 0: RETURN (True, f"no known vulnerabilities; SBOM written to {sbom_path}")
      RETURN (False, audit stderr/stdout tail)
    CATCH OSError|TimeoutExpired as e: RETURN (False, f"audit execution failed: {e}")
    FINALLY: os.unlink(req_path) (missing_ok)
  END

제약/근거:
  --frozen      : uv.lock 그대로 읽기 — lock 갱신/sync 차단 (잠긴 exe 재설치 방지, check_ruff --no-sync와 동일 근거)
  --no-dev      : 릴리스 아티팩트 공급망만 감사 (pytest 등 dev 그룹 제외)
  --no-deps     : uv export가 전체 전이 의존성을 이미 포함 — pip-audit 재해석 차단
  -f cyclonedx-json -o : 감사와 SBOM 생성을 단일 패스로 (§4.2-2 두 요구 동시 충족)
  네트워크      : pip-audit는 PyPI advisory DB 조회 필요 — 오프라인 시 (False, ...) 경로로 자연 강등

main(): 6종 체크로 확장 — [source control, LOC, ruff, supply chain audit, tests, smoke]
```

**의도적 미적용**: §4.2-1의 "origin synchronization" 검사는 추가하지 않음 —
릴리스 검증이 네트워크 단절 환경에서도 결정론적으로 동작해야 하며(`--frozen`과 동일 철학),
push 여부는 git hosting 측 CI의 책임.

### 13.5 검증 게이트

- 신규 테스트: A1(도구 실행 실패) / A2(export 실패) / A3(정상 + 플래그 검증) / A4(취약점 발견) / M3(main 6종)
- 구 메타 테스트 2건 삭제 후 전체 그린 + `prepare_release.py` 실측 6종 통과
- 소스/테스트 파일 모두 <500 LOC 유지

### 13.6 완료 결과 (2026-06-12)

| 항목 | Before | After |
|------|--------|-------|
| 테스트 수 | 128 | 130 (메타 2건 삭제, check_audit 4건 + main 1건 추가) |
| prepare_release 체크 | 5종 | 6종 (+ `check_audit` §4.2-2) |
| §4.2 준수 | ⚠️ 부분 (공급망 감사 부재) | ✅ 준수 (origin sync 의도적 미적용) |
| 공급망 실측 | — | 68 컴포넌트 무취약점, CycloneDX 1.4 SBOM (`sbom.json`, gitignored) |
| 프로젝트 의존성 | fastmcp + pydantic | 불변 (`uvx` 격리 실행 — Lightweight 유지) |

전 슬라이스 RED→GREEN 로그 실측, 슬라이스별 커밋 (A1/A2/A3/A4/M3).

---

## 14. v0.34 외부 리뷰 triage (2026-06-12)

외부 리뷰 4종(평가자 3인 종합 보고 포함)에 대한 판정 기록. 코드 불변 — 부채 등재와 포지셔닝 명문화만 수행.

### 14.1 수용 — 부채 등재

| 지적 | 리뷰 합의 | 판정 | 조치 |
|------|----------|------|------|
| `context_pressure`가 노드 수 기반 — 실제 토큰 압박과 무관 | 2~3/3 | **타당.** 15×passthrough → false high, 7×1500자 → false low. `tokens_original/tokens_saved` 컬럼이 기 저장돼 전환 비용 낮음 | TD-11 신규 (우선순위 20 — 차기 최우선) |
| outputSchema 미정의(TD-9)가 실질 최대 부채 | 2/3 | 방향 동의 — 다중 클라이언트/UI 통합 시 영향 상향 | TD-9 영향도 2→3 (우선순위 12) |
| INVALIDATED/ccr_store 물리 누적 | 1/3 강조, 2/3 낮게 평가 | 사실이나 실위험 낮음 — nodes는 UNIQUE upsert로 행 수 불변, 누적 대상은 ccr_store의 distinct payload 버전뿐(≤1500자) | TD-12 신규 (우선순위 9, Phase 3) |
| 압축 품질(인지 효용) 측정 부재 | 1/3 강조 + 1/3 부분 반론 | 측정 부재는 사실. 단 LLM-judge 없인 정량화 불가 — 경량 원칙과 충돌 | TD-13 신규 (보류, 우선순위 4) |

### 14.2 반박 / 사실관계 정정 (코드 근거)

| 리뷰 주장 | 정정 |
|----------|------|
| "매 응답마다 `dag_health`·`restoration_manifest` 등 방대한 제어 데이터 주입 — 어텐션 왜곡" | **사실과 다름.** think 응답은 `{status, node, thought_type, ccr_hash, compression, next_hint, context_pressure}` (+요청 시 parent_context)만 반환 — `dag_health`/`restoration_manifest`는 `status` 액션 한정 (src/think.py `_action_think` 반환부, src/actions.py `_action_status`) |
| "강제력 부재 — 경고만 하고 차단 못함" (전면화) | **부분 정정.** 구조 위반은 하드 차단됨: 사이클(ValueError→ToolError, protocol-level isError), 입력 경계 8종(payload 80–1500자 등), 미존재 노드 invalidate. 소프트인 것은 '수렴 행동' 유도뿐 — 가설 분기·재시작이 본질인 DAG 추론을 스키마로 강제하면 도구 목적과 모순. 의도적 포지셔닝 (리뷰들 스스로 "결함이 아니라 포지셔닝 차이"로 합의) |
| "압축 과정에서 핵심 맥락 누적 유실 위험" | **부분 정정.** 압축본은 parent_context 힌트이고 원본은 ccr_store에 byte-identical 보존(C17 검증), Live-Zone 원칙으로 작성 중 노드 비압축, <100자·절약<10%는 passthrough. 의료/법률 도메인 주의 권고 자체는 타당하나 '유실'은 비가역이 아님 |
| "무효화 루프 시 전체 스캔 성능 저하" | **부분 정정.** 동일 이름 재생성은 upsert(UNIQUE(session_id, name))라 행 증가 없음, 상태 조회는 `idx_nodes_session_status` 인덱스 경유. 잔여 우려는 TD-12로 등재 |
| "TD-10 미상" (review-2) | TD-10 = pyproject 버전 인상 대기 — §10에 공개된 항목 (리뷰어가 PLAN §10 미열람) |
| "WSL2 + uv 환경 전제" (review-4) | 현 개발·실측 환경은 Windows 11 네이티브 (원칙 0의 WSL2 기술은 v0.1 초기 기록 — 갱신 대상) |

### 14.3 합의 채택 — 포지셔닝 명문화 (3/3)

dag-thinking은 sequential-thinking의 **대체재가 아닌 다른 층위의 보완재**다:
- sequential-thinking — 노드 내부(intra-node) 추론 강제, 짧은 고강도 세션, 하드 가드레일
- dag-thinking — 세션 토폴로지·컨텍스트 관리(CCR), 장기 비선형 추론, 가역성·감사 가능성

권장 구성은 **병행**: 각 노드 작성 시 sequential-thinking으로 내부 추론을 강제하고,
DAG 골격과 컨텍스트 압축은 dag-thinking이 담당. 부적합 환경(순간적 단발 추론,
불안정한 소형 모델, 압축 힌트 소비가 부적절한 의료/법률 원문 처리)에서는 도입하지 않는다.

### 14.4 추가 리뷰 판정 — ccr_hash 알고리즘 (SHA-256 truncation vs xxHash)

질문: "어차피 24자로 자를 거면 SHA-256 계산량이 줄지도 않는데, 그냥 xxHash가 낫지 않나?"
판정: **현행 유지 (기각).**

- **절단의 목적은 계산 절약이 아니라 응답 토큰 절약** — hash는 매 think 응답과 status
  매니페스트의 노드별 `restore_cmd` 문자열에 노출된다. 64 hex 전체 사용 시 10-노드 세션의
  status 응답에서 hash만 640자. truncated SHA-256은 git short-hash와 동일한 표준 관행
  (절단 후에도 균등 분포 유지).
- **실측 (Windows 11, SHA-NI 가속, 1500B 입력)**: `sha256[:24]` 2.40µs vs
  `blake2b(digest_size=12)` 2.98µs. think 1회당 해시 1번 — SQLite 쓰기(ms 단위)와 압축
  regex가 지배하므로 해시는 호출 비용의 ~0.1% 미만. xxHash로 10배 줄여도 체감 0.
- **xxHash는 stdlib 부재** — 3rd-party C extension 의존 추가는 경량 원칙(§9.4) 위반 (결정적 사유).
- **충돌 저항은 성능이 아닌 정확성 속성**: ccr_store는 content-addressed
  (`PRIMARY KEY(hash, session_id)` + `INSERT OR IGNORE`)라 동일 세션 내 충돌 시 다른 노드의
  원본이 반환돼 byte-identical 복원 보장(C17)이 조용히 깨진다. 96-bit 절단 SHA-256은
  우연·의도 충돌 모두 ~2^48 난이도. 비암호 xxHash는 의도적 충돌 생성이 trivial —
  입력이 LLM 세션 텍스트이므로 프롬프트 주입으로 가역성을 오염시킬 공격면이 생긴다.
- "계산해 놓고 버린다"는 미감이 문제라면 stdlib 대안은 `blake2b(digest_size=12)`(절단 없음)
  이나, 실측상 더 느리고 기존 DB의 hash 호환성(C13 결정론)을 깨므로 비채택.

**추가 전수 검토 (2026-06-13)** — "sha256 외 대안은 고려 대상이 아닌가"에 대한 답.

요구조건: ① 결정론(C13 — 동일 payload → 동일 hash, content-addressed dedup의 전제)
② 충돌 저항(C17 — 충돌 = 잘못된 원본 복원) ③ stdlib only(§9.4) ④ 짧은 표기(응답 토큰)
⑤ 기존 DB hash 호환. 실측 환경: Python 3.13.12 / Windows 11 / SHA-NI, 1500B 입력.

| 후보 | 실측 | 판정 |
|------|------|------|
| crc32 (zlib) | 0.96µs | 탈락 — 선형 오류검출 코드라 충돌 저항 0(임의 충돌 생성 trivial), 32bit는 생일 한계 2^16. crc64/128/256은 stdlib 부재 |
| md5[:24] / sha1[:24] | 3.44 / 2.31µs | 탈락 — chosen-prefix 충돌 공격 실증된 깨진 원시. md5는 sha256보다 느리기까지 함. FIPS 환경 md5 차단 이슈 |
| **sha256[:24] (현행)** | **2.35µs** | **유지 — stdlib 암호 해시 중 실측 최속 (SHA-NI 하드웨어 가속)** |
| sha512 / sha3_256 / shake_128(12B) / blake2b(12B) / blake2s(12B) | 2.94~5.55µs | 적합하나 동급 — 96bit 출력에서 충돌 저항 동일(생일 2^48). 전부 sha256보다 느림. 교체 이득 0 + 기존 DB 마이그레이션 비용만 발생 |
| uuid4 / uuid6 / uuid7 / uuid8 | — | 범주 오류 — 랜덤/시간 기반 **비결정론**: 동일 payload 재생성 시 값이 바뀌어 C13 위반, ccr_store dedup·복원 체계 파괴. 식별자(row ID)용이지 콘텐츠 주소용이 아님. uuid6/7/8은 Python 3.14 신규 — 3.13 stdlib 부재 실측 |
| uuid5 / uuid3 | 5.71µs | 탈락 — 내부가 sha1/md5 + 122bit 절단: "더 약한 해시로 똑같이 절단하는" 구성. 표기도 36자(hyphen)로 24 hex보다 토큰 1.5배 |
| Ed25519 (`cryptography`) | — | 범주 오류 — 서명이지 해시가 아님: 개인키 관리 필요, "누가 썼나"를 증명하지 "무엇인가"를 주소화하지 않음. 내부적으로 sha512 사용, 서명 64B=128 hex, C-extension 의존(§9.4 위반). 변조 방지가 목표라면 stdlib `hmac`이 정답이나 로컬 SQLite에 해당 요구 없음 |
| xxhash 설치 | — | 기각 — 기술적으로 가능하나 비용>이득: 절약 ~2µs/호출 vs C-extension 공급망 표면 추가(§4.2-2 pip-audit/SBOM 감사 대상 증가) + 비암호 해시로 C17 보장 등급 하락 |

정정 2건: ① 96bit 절단의 절대적 충돌 저항은 생일 한계 ~2^48로 암호학적 기준 '중간'이나,
복합 PK `(hash, session_id)`가 충돌 피해를 해당 세션 내부로 국한 — 공격자가 오염시킬 수 있는
대상이 자신이 이미 통제하는 세션뿐이므로 위협 모델 대비 적정. ② xxHash 기각의 1순위 사유는
충돌 저항이 아니라 **의존성 원칙 + 이득 부재**가 정확한 순서다.

**마이그레이션 비용 논거의 강등 (2026-06-13 후속 리뷰)**: 개발 단계라 DB(`*.db` gitignored)는
일회용 — 마이그레이션 비용은 사실상 0이 맞다는 지적을 수용, 해당 논거를 결정 근거에서 제외한다.
단 이는 동급 후보(sha2/sha3/shake/blake2) 간 tie-breaker였을 뿐이며, **비용 0의 그린필드
기준으로 재선정해도 결과는 동일**하다:
- 실측 최속 — sha256 2.35µs < blake2b-12 2.94µs < shake_128 4.51µs (SHA-NI 보급으로
  현대 x86/ARM 모두 동일 경향)
- 보편성·외부 검증성 — `sha256sum | cut -c1-24`로 어느 환경에서나 재계산 가능.
  content-addressing 생태계의 사실상 기본값 (OCI digest, git SHA-256 mode, Nix, uv.lock)
- 절단은 교정할 결함이 아님 — NIST SP 800-107이 승인하는 표준 기법이고 SHA-224 자체가
  절단된 SHA-256이다. "절단 없는" blake2b-12로의 교체는 미감 외 기능 이득이 없는 수평 이동
- YAGNI — 요구가 없는 수평 교체는 churn. lock-in이 없다는 사실(비용 0)은 미래에 실제 요구
  (keyed hash/변조 방지 → blake2b keyed/hmac, hot path 대량 해싱 + 의존성 정책 변경 →
  BLAKE3/xxhash)가 생겼을 때 그때 바꿔도 싸다는 뜻 — 선제 교체의 근거가 아니라 반대 근거

---

## 15. v0.35 스펙 — Skeleton 재검증 3차 (2026-06-13)

### 15.1 배경 및 리뷰 판정

리뷰 기준: mcp-builder 스킬(Python/FastMCP 품질 체크리스트) + docs/MCP_Best_Practices_and_Lessons.md
전면 재대조 (v0.31·v0.33에 이은 3차). 실측 베이스라인: 130 tests 그린(6.36s), ruff 0 violations,
`grep "print(" src/` 0건, 전 소스 <500 LOC.

판정: **신규 표준 위반 0건** — §9 준수 현황표 그대로 유지. 소스 5-모듈 구조는 이미 핵심 로직
뼈대만 남은 상태로, 구조 변경 없음. 본 사이클의 실행 항목은 아래 잔여물 2건 + 문서 스테일 정정이다.
잔여 부채(TD-6/9/10/11/12/13)는 §10 로드맵 불변 — TD-10(pyproject 버전 인상)은 MCP 서버
프로세스가 exe를 잠그는 동안 보류 원칙 유지(본 사이클 중 서버 기동 상태 확인됨).

### 15.2 테스트 정리 (§12.2-3 중복 — 테스트를 위한 테스트)

| 대상 | 근거 |
|------|------|
| `test_prepare_release.py::test_m0_main_runs_six_checks` + `test_m1_all_checks_pass_returns_zero` | §12.2-3 중복 — 동일 시나리오(전 체크 통과, 동일 `_patch_all_pass` 픽스처)를 출력 단언/종료코드 단언 2건으로 분할 재검증. 1건으로 통합: exit 0 + 6×[PASS] + [FAIL] 부재 + ruff/audit 명명을 단일 테스트가 단언 |

그 외 전 파일 재감사 결과 §12.2 위반 재유입 없음 — `_split_sentences` 회귀 가드(§12.2 유지 예외),
MCP 프로토콜 표면 계약 테스트(스키마·annotations·instructions — 클라이언트 노출 표면), S1 smoke는 유지.
130 → 129 tests.

### 15.3 소스 스켈레톤 정리 (REFACTOR — 동작 불변)

- `think.py` `_action_think`: `delta = 0` dead init 제거 — 유일한 읽기 지점
  (`session_total_saved = prev_session_total + delta`)에 도달하는 모든 경로가 트랜잭션 내
  `delta = tokens_saved - old_tokens_saved` 할당을 선행하며, 트랜잭션 예외 시 함수 자체를 탈출.

### 15.4 문서 스테일 정정

- README.md: `tests/test_server.py::TestThinkStatusRestoreRoundtrip` 예시 — v0.32에서 폐기된
  파일 경로. 실재 스위트 기준으로 교정.
- PLAN.md §6: LOC 실측 정정 — db.py 156→153, prepare_release.py 157→184(v0.33 check_audit 반영),
  think.py 382→381(§15.3 반영).

### 15.5 검증 게이트

- 전체 그린(129 tests) + ruff 0 violations + 전 파일 <500 LOC 유지
- 슬라이스별 커밋: 스펙(§15) → 테스트 통합 → 소스 정리 → 집계 동기화

---

**조정 완료 요약:**
- 툴 5개 → **1개** (`dag_thinking(action=...)`)로 건너뛰기 문제 구조적 차단
- `depends_on` 지정 시 부모 압축 페이로드 **자동 내장** → 별도 resolve 호출 불필요
- `status()` 항상 **복원 매니페스트** 포함 + 복붙 가능한 `restore_cmd` 제공
- `restore(hash=None)` → 전체 목록, `restore(hash=X)` → 원본 반환으로 완전 가역성 보장
- 구현 태스크 27개 + 검증 체크리스트 23개 + 구현 요청 프롬프트 완비

---

## 16. v0.36 스펙 — TD-9/TD-10/CLEAN-3 해소 (2026-06-13)

### 16.1 배경 및 목표

mcp-builder 전면 리뷰(v0.35 사이클) 결과 확인된 3개 잔여 항목을 TDD 슬라이스 단위로 해소.
기존 130 tests가 전 슬라이스의 회귀 가드 역할. 신규 행위 변경 없음.

### 16.2 슬라이스 목록

| 슬라이스 | 분류 | 항목 | 결과 |
|---------|------|------|------|
| Slice 1 | TD-10 | pyproject.toml 버전 0.30→0.35 인상 + `test_td10_version_matches_document_version` 추가 | ✅ 129→130 tests |
| Slice 2 | CLEAN-3 | `_compute_dag_health` think.py→actions.py 이전 (SRP: 정의 위치 = 사용 위치) | ✅ 130 tests 불변 |
| Slice 3 | TD-9 | TypedDict 반환 타입 정의 — `ThinkResult`(think.py), `StatusResult`/`InvalidateResult`/`RestoreListResult`/`RestorePayloadResult`/`InfoResult`(actions.py) | ✅ 130 tests 불변 |

### 16.3 구조 변경 요약

- `think.py`: `from collections import deque` 제거, `from typing import TypedDict` 추가, `ThinkResult` 정의, `_compute_dag_health` 삭제
- `actions.py`: `import sqlite3`, `from collections import deque`, `from typing import TypedDict` 추가, 5개 TypedDict 정의, `_compute_dag_health` 수용, 함수 반환 어노테이션 전체 갱신
- `tests/test_dispatcher.py`: `test_td10_version_matches_document_version` 추가 (TD-10 회귀 가드)

### 16.4 검증 게이트

- 130 tests GREEN + ruff 0 violations + 전 파일 <500 LOC
- 커밋 3건: `fix(TD-10)`, `refactor(CLEAN-3)`, `feat(TD-9)`

---

## 17. v0.37 스펙 — TD-11 context_pressure 토큰 기반 전환 (2026-06-13)

### 17.1 배경

외부 리뷰(v0.34 §14.1) 2~3인 합의 부채. `context_pressure`가 `COUNT(COMPLETED)` 노드 수를 압박 신호로 사용하나, 이는 실제 토큰 압박의 부정확한 대리값이다:
- `15 × passthrough(80자)` → false HIGH (노드 15개지만 토큰은 300개)
- `7 × 1500자` → false LOW (노드 7개지만 토큰은 2625개)

`nodes.tokens_original` 컬럼이 기 저장돼 `SUM` 1-query 전환 비용이 낮다.

### 17.2 변경 내용

| 항목 | Before | After |
|------|--------|-------|
| 신호 | `COUNT(*) WHERE status='COMPLETED'` | `SUM(tokens_original) WHERE status='COMPLETED'` |
| 임계값 | `_PRESSURE_MEDIUM=8` (노드), `_PRESSURE_HIGH=15` (노드) | `_PRESSURE_MEDIUM_TOKENS=900`, `_PRESSURE_HIGH_TOKENS=1700` |
| 반환 키 | `{"level", "node_count", "hint"}` | `{"level", "tokens_original", "hint"}` |
| 힌트 문구 | "Session has X nodes ..." | "Session has accumulated X tokens ..." |

임계값 근거: PAYLOAD(465자) = 116 tokens. 8×116=928≥900(medium), 7×116=812<900(low), 15×116=1740≥1700(high) — 기존 경계 행위 보존.

### 17.3 테스트 변경 (test_think.py::TestContextPressure)

| 구 테스트 | 신 테스트 | 변경 내용 |
|----------|---------|---------|
| `test_first_node_low` (C36) | `test_first_node_low` (C36) | `node_count=1` → `tokens_original>0`, `node_count not in cp` 추가 단언 |
| `test_boundary_8_nodes_medium` (C37) | `test_boundary_medium_tokens` (C37) | `node_count=8` → `tokens_original=928` |
| `test_boundary_15_nodes_high` | `test_boundary_high_tokens` | level 검증 불변 |
| `test_invalidated_nodes_excluded` (P3-9) | `test_invalidated_nodes_tokens_excluded` (P3-9) | `node_count=7` → `tokens_original=812` |

### 17.4 검증 게이트

- 130 tests GREEN (테스트 수 불변 — 4건 교체)
- 커밋 1건: `feat(TD-11)`

---

## 18. v0.38 스펙 — CLEAN-4 ThinkResult 타입 강화 + DOC-2 주석 정리 (2026-06-13)

### 18.1 CLEAN-4: ThinkResult TypedDict 키 정확도

**문제:** `ThinkResult(TypedDict, total=False)` — 8개 키 전부 `__optional_keys__`에 분류됨.
실제로 `parent_context`만 선택적(`depends_on` 없을 때 미포함)이고 나머지 7개 키는 항상 반환.

**수정:**
```python
# Before
class ThinkResult(TypedDict, total=False):
    ...
    parent_context: dict

# After
from typing import NotRequired, TypedDict

class ThinkResult(TypedDict):          # total=True (default)
    status: str
    node: str
    thought_type: str
    ccr_hash: str
    compression: dict
    next_hint: str
    context_pressure: dict
    parent_context: NotRequired[dict]  # 유일한 선택적 키
```

### 18.2 DOC-2: WHAT 주석 제거

`_validate_think_inputs` 함수 docstring `"""action='think' 입력 유효성 검사. 실패 시 ValueError 즉시 raise."""`
함수 이름·시그니처로 자명 → CLAUDE.md 주석 원칙 준수 제거.

### 18.3 검증 게이트

- 131 tests GREEN (+1: `TestThinkResultTyping::test_parent_context_is_only_optional_field`)
- 커밋 1건: `refactor(v0.36): CLEAN-4 ThinkResult 타입 강화 + DOC-2 WHAT 주석 제거`

---

## 19. v0.39 스펙 — CLEAN-6 RestorePayloadResult 타입 강화 + CLEAN-7 주석 정리 (2026-06-13)

### 19.1 CLEAN-6: RestorePayloadResult TypedDict 키 정확도

**문제:** `RestorePayloadResult(TypedDict, total=False)` — 4개 키 전부 `__optional_keys__`에 분류.
`node_name`, `original_payload`, `tokens`는 항상 반환되고 `warning`만 조건부(삭제 노드·INVALIDATED).

**수정:** `total=True`(기본) + `warning: NotRequired[str]`

### 19.2 CLEAN-7: compressor.py WHAT 주석 4건 제거

| 제거된 주석 | 이유 |
|-----------|------|
| `_is_cjk_char` docstring (caller reference) | 함수명으로 자명 + CLAUDE.md "callers 참조 금지" |
| `# position bonus: first and last sentences are important` | 코드가 직접 설명 |
| `# thought_type별 추가 키워드 가중치` | 변수명으로 자명 |
| `# passthrough if savings < threshold` | 조건식이 직접 설명 |

보존: `# \b\w+\b collapses an entire CJK run to one "word" — use char count instead` (비자명 WHY)

### 19.3 검증 게이트

- 132 tests GREEN (+1: `TestRestorePayloadResultTyping::test_warning_is_only_optional_field`)
- 커밋 1건: `refactor(v0.39): CLEAN-6 RestorePayloadResult 타입 강화 + CLEAN-7 WHAT 주석 제거`
