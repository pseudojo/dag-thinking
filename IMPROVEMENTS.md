# dag-thinking 개선 이력

> 모든 항목 구현 완료 (v0.3 ~ v0.7). 상세 설계는 PLAN.md, 구현은 src/server.py · src/compressor.py 참조.

---

## 구현 완료 목록

| ID | 내용 | 버전 | 관련 파일 |
|----|------|------|-----------|
| I01 | `_has_cycle` 리팩토링 — dead code 제거, 단일 DFS | v0.3 | server.py |
| I02 | think 응답에 `compression.session_total_saved` 추가 | v0.3 | server.py |
| I03 | `invalidate` — `target_node` 존재 여부 검증 + ValueError | v0.3 | server.py |
| I04 | `status` — `dag.nodes`에 `created_at` 필드 노출 | v0.3 | server.py |
| I05 | `next_hint` — thought_type별 컨텍스트 힌트 동적화 | v0.4 | server.py |
| I06 | thought_type별 키워드 가중치 (`_TYPE_KEYWORDS`) — 압축 특화 | v0.4 | compressor.py |
| I07 | 세션 컨텍스트 압박 경고 (`context_pressure`) | v0.4 | server.py |
| I08 | DAG 수렴 상태 진단 (`dag_health`) | v0.4 | server.py |

---

## 추가 품질 개선 (v0.5 ~ v0.7)

| ID | 내용 | 버전 |
|----|------|------|
| Q-1 | `session_total_saved` 델타 공식 버그 수정 | v0.5 |
| Q-2 | edge 배치 조회 분리 — N×DB → 1×DB | v0.5 |
| Q-3 | `_validate_think_inputs` SRP 분리 | v0.5 |
| Q-4 | import 가드 수정 (`from src.compressor import`) | v0.5 |
| Q-5 | `_NEXT_HINTS` dead fallback 제거 | v0.5 |
| Q-6 | 태스크 트래킹 주석 제거 | v0.5 |
| R-EDGE | 엣지 삭제 방향 버그 — `WHERE parent=?` → `WHERE child=?` | v0.6 |
| R-CCR | `ccr_store` 복합 PK `(hash, session_id)` + `INSERT OR IGNORE` | v0.6 |
| CLEAN-1 | `_has_cycle()` 데드 코드 30줄 삭제 | v0.6 |
| CLEAN-2 | 모듈 상수 순서 정규화 | v0.6 |
| SEC-1 | `_action_restore` 에러 경로에서 타 세션 ID 노출 차단 | v0.7 |
| PERF-1 | `compress()` / `estimate_tokens()` DB 쓰기 락 밖으로 이동 | v0.7 |
| PERF-2 | `_action_status` / `_action_restore` 트랜잭션 범위 최소화 | v0.7 |
| TYPE-1 | `_db()` / `_compute_dag_health()` 타입 어노테이션 완성 | v0.7 |

---

## 검증 체크리스트

모든 항목 GREEN · 181 tests passed (v0.7 기준)

```
[I01 — cycle detection]                         [v0.3 ✅]
✅ IC01. A→B→A 시도 → ValueError
✅ IC02. 자기 참조 (A depends_on A) → ValueError
✅ IC03. 3-hop 전이 사이클 (A→B→C, C depends_on A) → ValueError
✅ IC04. 다이아몬드 구조 (A→B, A→C, B→D, C→D) → OK

[I02 — session_total_saved]                     [v0.3 ✅]
✅ IC05. think 응답에 compression.session_total_saved 필드 존재
✅ IC06. 두 번째 think 후 session_total_saved >= 첫 번째
✅ IC07. passthrough 노드도 session_total_saved 포함

[I03 — invalidate node existence]               [v0.3 ✅]
✅ IC08. 존재하지 않는 노드 invalidate → ValueError
✅ IC09. 에러 메시지에 target_node 이름 포함
✅ IC10. 기존 노드 invalidate 동작 회귀 없음

[I04 — created_at in status]                    [v0.3 ✅]
✅ IC11. status().dag.nodes[*]에 created_at 필드 존재
✅ IC12. created_at이 None이 아닌 문자열

[I05 — next_hint]                               [v0.4 ✅]
✅ IC13. Objective 노드 → hint에 'Hypothesis' 또는 'Assumption' 포함
✅ IC14. Synthesis 노드 → hint에 'Action' 또는 'status' 포함
✅ IC15. Action 노드 → hint에 'status()' 포함

[I06 — thought_type keyword scoring]            [v0.4 ✅]
✅ IC16. extra_keywords 파라미터 → 스코어 향상 확인
✅ IC17. Evidence 문장 → _TYPE_KEYWORDS["Evidence"]로 스코어 향상
✅ IC18. Synthesis 문장 → _TYPE_KEYWORDS["Synthesis"]로 스코어 향상
✅ IC19. compress(text, "Evidence") — 파라미터 정상 수용
✅ IC20. think(Evidence 타입) → compression 정상 동작

[I07 — context_pressure]                        [v0.4 ✅]
✅ IC21. think 응답에 context_pressure 필드 존재
✅ IC22. 첫 번째 노드 → context_pressure.level == "low"
✅ IC23. _PRESSURE_MEDIUM 이상 노드 → level이 "medium" 또는 "high"
✅ IC24. context_pressure에 node_count, hint 필드 존재

[I08 — dag_health]                              [v0.4 ✅]
✅ IC25. status 응답에 dag_health 필드 존재
✅ IC26. Synthesis 없는 세션 → is_converging == False
✅ IC27. Synthesis 노드 추가 후 → is_converging == True
✅ IC28. 연결 없는 2개 노드 → orphan_nodes 포함
✅ IC29. A→B→C 체인 → max_depth == 2
```
