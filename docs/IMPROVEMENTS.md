# dag-thinking 개선 이력

> v0.3 ~ v0.34 전체 개선 항목 등재 (v0.31 TD-2 해소 — 기존 미등재 시리즈 포함).
> 상세 설계는 PLAN.md, 구현은 `src/` 5개 모듈 참조. 130 tests passing (v0.34 기준).
>
> **주**: 아래 표의 I/Q/P 시리즈를 검증하던 버전별 테스트 파일은 v0.32에서 행위 기준
> 8개 파일로 재구성됐다 (PLAN.md §12). 각 항목의 행위는 신규 스위트가 계속 보장한다.

---

## I 시리즈 — 기능 개선 (v0.3 ~ v0.18)

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
| I09 | `_compute_context_pressure()` 쓰기 트랜잭션 밖으로 이동 (PERF-2 완성) | v0.8 | server.py |
| I10 | `_compute_dag_health()` INVALIDATED 경유 엣지 BFS 제외 버그 수정 | v0.8 | server.py |
| I11 | `_split_sentences()` 추출 + 유니코드 문장 구분자 (。！？) 지원 | v0.8 | compressor.py |
| I12 | `_split_sentences()` CJK 공백 없는 즉시 분리 | v0.9 | compressor.py |
| I13 | `_is_list_content()` `·` (U+00B7) middle dot 오탐 제거 | v0.9 | compressor.py |
| I17 | `depends_on` 길이 상한 `_MAX_DEPENDS_ON=20` | v0.9 | server.py |
| I18 | `estimate_tokens()` CJK Extension A/Compatibility/SMP 범위 보완 | v0.10 | compressor.py |
| I20 | `session_total_saved` SELECT 쓰기 트랜잭션 외부 이동 (PERF-2 완성) | v0.10–v0.11 | server.py |
| I21 | `_join_sentences()` 추출 + CJK 재결합 공백 제거 | v0.10 | compressor.py |
| I22 | `node_name` 길이 상한 `_MAX_NODE_NAME_LEN=200` | v0.10 | server.py |
| I23 | CJK Compatibility 범위 유니코드 이스케이프 교체 | v0.11 | compressor.py |
| I24 | `_score_sentence()` CJK-aware word_count | v0.11 | compressor.py |
| I25 | `_is_cjk_char()` 헬퍼 추출 — CJK 정의 통일 (DRY) | v0.12 | compressor.py |
| I28 | `_action_restore()` 2-query → LEFT JOIN 1-query 통합 | v0.12 | server.py |
| I29 | `depends_on` 중복 항목 순서 보존 제거 | v0.12 | server.py |
| I30 | `session_id` 길이 상한 `_MAX_SESSION_ID_LEN=200` | v0.12 | server.py |
| I31 | 공백 전용 payload 차단 (`payload.strip()` 검증) | v0.13 | server.py |
| I32 | `idx_edges_child` 인덱스 추가 (upsert 풀스캔 제거) | v0.13 | server.py |
| I33 | `_split_sentences` 줄임표(`...`) false-split 수정 | v0.13 | compressor.py |
| I34 | 엣지 삽입 루프 → `executemany` + 가드 명확화 | v0.13 | server.py |
| I35 | `_action_think` 읽기 쿼리 트랜잭션 외부 이동 (PERF-2 완성) | v0.14 | server.py |
| I36 | `note` 길이 상한 `_MAX_NOTE_LEN=500` | v0.14 | server.py |
| I37 | `_compress_list` 최소 k=2 (과잉 압축 방지) | v0.14 | compressor.py |
| I38 | `_split_sentences` 줄임표+공백 false-split 수정 (2-char lookbehind) | v0.15 | compressor.py |
| I39 | `_compress_prose` 최소 k=2 | v0.15 | compressor.py |
| I40 | `depends_on` 빈 경우 cycle check 스킵 | v0.15 | server.py |
| I41 | `_action_invalidate` target_node 공백 전용 방어 | v0.15 | server.py |
| I42 | think 응답에 `thought_type` 필드 추가 | v0.16 | server.py |
| I43 | status `dag.nodes`에 `ccr_hash` 필드 추가 | v0.16 | server.py |
| I44 | `_is_list_content` `+` GFM 불릿 지원 | v0.16 | compressor.py |
| I45 | `_compute_dag_health` `total_nodes` 추가 | v0.16 | server.py |
| I46 | `note=None` 방어 (None→"" 변환) | v0.17 | server.py |
| I47 | `target_node` 공백 정규화 (strip) | v0.17 | server.py |
| I48 | `_split_sentences` 복합 종결자 (?!/!? 등) 지원 | v0.17 | compressor.py |
| I49 | `_split_sentences` 약어 false-split 방지 (Mr./Dr.) | v0.18 | compressor.py |
| I50 | cycle check 트랜잭션 내부 이동 | v0.18 | server.py |
| I51 | `node_name` 공백 정규화 (strip) | v0.18 | server.py |
| I52 | restore 시 삭제 노드 warning | v0.18 | server.py |
| I53 | `_cascade_invalidate` BFS 개선 | v0.18 | server.py |

---

## Q / R / CLEAN / SEC / PERF / TYPE 시리즈 — 품질·성능·보안 (v0.5 ~ v0.7)

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

## P / BUG / R2-R4 / STYLE / QUAL 시리즈 — 버그 수정·리팩토링 (구 미등재분, v0.31 TD-2 해소로 등재)

> 테스트 파일: `test_p1_p2_p3.py`, `test_bugfixes.py`, `test_quality_improvements.py`, `test_style_and_refactor.py`

| ID | 내용 | 관련 테스트 |
|----|------|------|
| BUG-1 | 노드 업데이트 시 `tokens_saved` 이중 집계 수정 | test_bugfixes.py |
| P1-2 | orphan edge 방지 — 존재하지 않는 parent(`ghost`) depends_on 시 edge INSERT 스킵 | test_p1_p2_p3.py |
| P1-3 | `restore_cmd` single-quote 이스케이프 — `repr()` 사용으로 valid Python 보장 | test_p1_p2_p3.py |
| P2-1 | `thought_type_distribution`에서 INVALIDATED 노드 제외 | test_p1_p2_p3.py |
| P2-2 | 노드 업데이트 시 ccr_store 구 hash 보존 (content-addressed) | test_p1_p2_p3.py |
| P2-3 | 노드 재생성 시 stale edge 정리 + outgoing edge 보존 | test_p1_p2_p3.py |
| P2-4 | status metrics에서 INVALIDATED 노드 제외 | test_p1_p2_p3.py |
| P2-6 | `idx_nodes_session_status` 복합 인덱스 추가 | test_p1_p2_p3.py |
| P3-1 | `restore_cmd` 포맷 통일 — `action='restore', ` 공백 포함 | test_p1_p2_p3.py |
| P3-3 | `how_to_restore` 템플릿을 `restore_cmd`와 동일 포맷으로 통일 | test_p1_p2_p3.py |
| P3-9 | `context_pressure` COUNT에서 INVALIDATED 노드 제외 | test_bugfixes.py |
| P3-12 | blank/whitespace `node_name`·`session_id` ValueError (tab/newline 포함) | test_bugfixes.py |
| R-2 | `init_db` DDL 트랜잭션 안전화 — `executescript` 제거, 새 컬럼 추가 | test_quality_improvements.py |
| R-3 | 노드별 `tokens_original`/`tokens_saved` 컬럼 저장 — status payload 스캔 제거 | test_quality_improvements.py |
| R-4 | `_resolve_parent_context` 독립 함수 추출 (SRP) | test_quality_improvements.py |
| STYLE-1 | `ruff check src/` 0 violations (E/F/I 룰셋) | test_style_and_refactor.py |
| QUAL-1 | `_is_list_content`/`_compress_list` 변수명 `l`→`line` rename | test_style_and_refactor.py |
| QUAL-2 | `found` 변수 인라인 리팩토링 | test_style_and_refactor.py |

---

## MCP 표준화 시리즈 (v0.19 ~ v0.30)

| 항목 | 내용 | 버전 |
|------|------|------|
| ToolAnnotations | readOnly/destructive/idempotent/openWorld 4종 | v0.19 |
| inputSchema Field descriptions | 10개 파라미터 전체 설명+제약 | v0.20–v0.24 |
| docstring 예시 | "Use when:/Don't use when:" 6개 예시 | v0.22 |
| async + 에러 처리 | `async def dag_thinking`, 서버명 `dag_thinking_mcp` | v0.25 |
| MCP Resource | `dag-thinking-session://{session_id}` | v0.26 |
| FastMCP instructions | XML 시맨틱 태그 (`<use_case>`, `<important_notes>`) | v0.27–v0.28 |
| 3-파일 분리 | db.py + actions.py + server.py (<500 LOC/파일) | v0.28 |
| action='info' | §3.2 진단 엔드포인트 — 동적 버전(importlib.metadata) | v0.28–v0.29 |
| think.py 추출 | actions.py 655→321 LOC | v0.29 |
| TD-5 ToolError | ValueError → `raise ToolError` → protocol-level isError | v0.30 |
| TD-7 prepare_release.py | §4.2 릴리스 검증 — git/LOC/tests/smoke 4종 | v0.30 |
| TD-4 import 정리 | `.compressor` 단일 relative import | v0.30 |
| TD-1 파일명 교정 | `test_i11_i12.py` → `test_restore_list_health.py` | v0.30 |
| TD-2 이력 등재 | IMPROVEMENTS.md 전면 갱신 — 미등재 시리즈 포함 | v0.31 |
| Skeleton 재구성 | 테스트 459→128 (행위 기준 8파일), 테스트를 위한 테스트 삭제 | v0.32 |
| TD-3 `__all__` 제거 | server/actions 재수출 제거, 테스트 직접 import | v0.32 |
| check_ruff | prepare_release §4.2-3 정적 분석 — 5종 체크 완성 | v0.32 |
| TD-8 check_audit | §4.2-2 공급망 감사 — `uv export --frozen` + `uvx pip-audit`, CycloneDX SBOM, 6종 체크 | v0.33 |
| 메타 테스트 정리 | §12.2-1 위반 재유입 2건 삭제(L5/R4) + 스테일 주석·dead param 제거 | v0.33 |
| 외부 리뷰 triage | 4종 리뷰 판정(PLAN §14) — TD-11/12/13 등재, TD-9 재평가, 반박 근거·포지셔닝 명문화 | v0.34 |
| ccr_hash 알고리즘 판정 | xxHash 제안 검토 — stdlib 14종+uuid+Ed25519 전수 실측, 현행 sha256[:24] 유지, revisit 트리거 명시 (PLAN §14.4) | v0.34 |

---

## 검증 상태

- **130 tests passing** (v0.34 기준, 2026-06-12 실측 — 행위 기준 8파일)
- `prepare_release.py` 6종 체크: source control / LOC limits / static analysis (ruff) /
  supply chain audit (pip-audit + SBOM) / test suite / MCP smoke test — 전부 PASS 실측
- 미해소 부채는 PLAN.md §10 참조 (TD-6, TD-9, TD-10, TD-11, TD-12 / 보류: TD-13)
