# dag-headroom 개선 명세

> TDD 흐름: 스펙 정의 → RED → GREEN → ALIGNMENT → REFACTOR
> PLAN.md 원칙 준수: lightweight, no new deps, single entry point 유지

---

## I01. `_has_cycle` 리팩토링 — dead code 제거, 단일 DFS

### 문제
현재 구현(server.py:94-153)에 3개의 DFS 루프가 존재한다.
첫 번째 루프(109-119)는 dead code: forward 그래프 없이 순회하려 해서 실제 사이클 감지를 하지 못한다.
나머지 두 루프가 우연히 올바른 결과를 내지만, 코드가 60줄에 걸쳐 불필요하게 복잡하다.

### 명세
- `new_parent == new_child` → 자기 참조 사이클, 즉시 True 반환
- 기존 forward 엣지로 `new_child`에서 출발해 `new_parent`에 도달하면 True
- 단일 DFS(또는 BFS) 구현, 코드 ≤ 20줄
- 3-hop 전이 사이클도 감지: A→B→C 존재 시 C depends_on A → 사이클

---

## I02. think 응답에 `session_total_saved` 추가

### 문제
PLAN.md 명세에 명시된 필드가 구현에서 누락됨:
```python
"compression": {
    "tokens_saved": 42,
    "session_total_saved": 187  # ← 누락
}
```

### 명세
- `action="think"` 응답의 `compression` 객체에 `session_total_saved` 필드 추가
- 값 = 현재 세션의 누적 `tokens_saved` (sessions 테이블)
- 첫 노드: `session_total_saved == tokens_saved`
- 두 번째 노드: `session_total_saved >= 이전 session_total_saved`

---

## I03. `action="invalidate"` — target_node 존재 여부 검증

### 문제
존재하지 않는 노드에 invalidate를 호출하면 에러 없이 `{"invalidated": []}` 반환.
PLAN.md C19 기준: "단일 노드 무효화 → status: INVALIDATED" — 이는 노드가 실제 존재하는 경우를 전제한다.

### 명세
- `target_node`가 해당 세션에 존재하지 않으면 `ValueError` 발생
- 에러 메시지에 `target_node` 이름과 `session_id` 포함
- 기존 노드 무효화 동작은 변경 없음 (회귀 없음)

---

## I04. `action="status"` — 노드에 `created_at` 포함

### 문제
status 응답의 `dag.nodes`에 생성 시각이 없어 디버깅 및 노드 순서 파악이 어렵다.

### 명세
- `dag.nodes` 각 항목에 `created_at` 필드 추가 (ISO 8601 문자열)
- 기존 필드(`name`, `thought_type`, `status`) 유지 (하위 호환)
- 스키마 변경 없음 (nodes 테이블에 이미 created_at 존재)

---

## I05. `next_hint` — thought_type 기반 컨텍스트 힌트

### 문제
현재 모든 노드에 동일한 hint 반환:
`"Add Evidence/Critique or call status() to close."`
LLM이 다음 단계를 더 명확히 알도록 thought_type별 가이던스가 필요하다.

### 명세
thought_type별 next_hint:
| thought_type | next_hint |
|---|---|
| Objective | "Add Hypothesis or Assumption nodes to explore this objective." |
| Hypothesis | "Add Evidence or Assumption nodes to support or challenge this hypothesis." |
| Assumption | "Add Evidence to validate, or Critique to challenge this assumption." |
| Evidence | "Add Synthesis to draw conclusions, or Critique to challenge the evidence." |
| Critique | "Add Synthesis to reconcile findings, or revise the critiqued node." |
| Synthesis | "Add Action nodes to operationalize insights, or call status() to close." |
| Action | "All conclusions reached. Call status() to review the full DAG." |

---

---

## I06. thought_type별 키워드 가중치 — ContentRouter 유사 압축 특화

### 문서 근거
"LLM 프롬프트 엔지니어링 심층 탐구" §1: ContentRouter가 입력 데이터 유형을 감지해
적절한 압축 엔진으로 라우팅. dag-headroom에서 thought_type이 그 유형 신호 역할을 한다.

### 문제
`IMPORTANCE_KEYWORDS`가 모든 thought_type에 동일하게 적용된다.
Evidence 노드 압축 시 "data", "measured", "observed" 같은 증거 특화 단어가
가중치를 받지 못해 중요 문장이 버려질 수 있다.

### 명세
- `compressor.py`에 `_TYPE_KEYWORDS: dict[str, frozenset]` 추가 (7개 타입)
- `_score_sentence(sentence, position, total, extra_keywords=frozenset())` — 파라미터 추가
  - `extra_hits = Σ(w in extra_keywords)` → score += extra_hits × 1.0
- `_compress_list`, `_compress_prose` — `extra_keywords` 전달
- `compress(text, thought_type=None)` — thought_type으로 extra_keywords 조회
- `server.py`: `compress(payload, thought_type)` 호출로 변경
- No new dependencies

---

## I07. 세션 컨텍스트 압박 경고 — think 응답에 context_pressure 추가

### 문서 근거
보고서 서론: "컨텍스트 사용량이 70~80% 시점부터 사전 예방적(Proactive)으로 작동하도록 설계.
컨텍스트가 한계에 도달한 시점은 이미 실패 경로다."

### 문제
현재 think 응답에 세션 규모 신호가 없어 LLM이 언제 Synthesis로 수렴해야 하는지 알 수 없다.
노드가 무한정 쌓이면 context window 과부하로 이어진다.

### 명세
- `_PRESSURE_MEDIUM = 8`, `_PRESSURE_HIGH = 15` 상수 추가
- `_compute_context_pressure(conn, session_id) -> dict` 추가
  - node_count: 현재 세션 전체 노드 수 (upsert 후 기준)
  - level: "low" (< MEDIUM) | "medium" (MEDIUM ≤ x < HIGH) | "high" (≥ HIGH)
- think 응답에 최상위 키 추가:
  ```
  "context_pressure": { "level": "low"|"medium"|"high", "node_count": N, "hint": "..." }
  ```
- No new dependencies

---

## I08. DAG 수렴 상태 진단 — status 응답에 dag_health 추가

### 문서 근거
"유한 시간 내 최적 상태로 수렴하는지 여부는 시스템의 안정성과 경제성을 결정짓는 핵심"
및 확률적 드리프트 부등식(동적 스케줄러 수렴 조건).

### 문제
status() 응답이 DAG 구조를 나열하지만, 추론이 수렴 중인지·고립 노드가 있는지·
체인 깊이가 얼마인지 LLM이 직접 계산해야 한다.

### 명세
- `_compute_dag_health(node_rows, edge_rows) -> dict` 추가
- status 응답에 `dag_health` 최상위 키 추가:
  ```
  {
    "is_converging": bool,            # Synthesis 또는 Action COMPLETED 존재
    "max_depth": int,                 # 루트에서 최장 추론 체인 깊이 (BFS)
    "orphan_nodes": list[str],        # 엣지 없는 고립 노드 (2+ 노드 세션에서)
    "thought_type_distribution": dict[str, int],
    "health_hint": str               # 상태 기반 행동 가이드
  }
  ```
- No new dependencies

---

## 검증 체크리스트

```
[ I01 — cycle detection ]
□ IC01. A→B→A 시도 → ValueError (기존 T23 회귀 없음)
□ IC02. 자기 참조 (A depends_on A) → ValueError
□ IC03. 3-hop 전이 사이클 (A→B→C, C depends_on A) → ValueError
□ IC04. 다이아몬드 구조 (A→B, A→C, B→D, C→D) → OK (사이클 아님)

[ I02 — session_total_saved ]
□ IC05. think 응답에 compression.session_total_saved 필드 존재
□ IC06. 두 번째 think 후 session_total_saved >= 첫 번째 session_total_saved
□ IC07. passthrough(tokens_saved=0) 노드도 session_total_saved 포함

[ I03 — invalidate node existence ]
□ IC08. 존재하지 않는 노드 invalidate → ValueError 발생
□ IC09. 에러 메시지에 target_node 이름 포함
□ IC10. 기존 노드 invalidate 동작 회귀 없음 (T24 재실행)

[ I04 — created_at in status ]
□ IC11. status().dag.nodes[*]에 created_at 필드 존재
□ IC12. created_at이 None이 아닌 문자열

[ I05 — next_hint ]
□ IC13. Objective 노드 → hint에 'Hypothesis' 또는 'Assumption' 포함
□ IC14. Synthesis 노드 → hint에 'Action' 또는 'status' 포함
□ IC15. Action 노드 → hint에 'status()' 포함

[ I06 — thought_type keyword scoring ]
□ IC16. _score_sentence(sentence, 0, 5, extra_keywords=frozenset({"data"})) > base score
□ IC17. Evidence 문장 → _TYPE_KEYWORDS["Evidence"]로 스코어 향상
□ IC18. Synthesis 문장 → _TYPE_KEYWORDS["Synthesis"]로 스코어 향상
□ IC19. compress(text, "Evidence") — 파라미터 정상 수용
□ IC20. think(Evidence 타입) → compression 정상 동작 (회귀 없음)

[ I07 — context_pressure ]
□ IC21. think 응답에 context_pressure 필드 존재
□ IC22. 첫 번째 노드 → context_pressure.level == "low"
□ IC23. _PRESSURE_MEDIUM 이상 노드 → level이 "medium" 또는 "high"
□ IC24. context_pressure에 node_count, hint 필드 존재

[ I08 — dag_health ]
□ IC25. status 응답에 dag_health 필드 존재
□ IC26. Synthesis 없는 세션 → is_converging == False
□ IC27. Synthesis 노드 추가 후 → is_converging == True
□ IC28. 연결 없는 2개 노드 → orphan_nodes 포함
□ IC29. A→B→C 체인 → max_depth == 2
```
