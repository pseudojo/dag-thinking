# dag-thinking 개선 이력

> v0.3 ~ v0.45 전체 개선 항목 등재 (v0.31 TD-2 해소 — 기존 미등재 시리즈 포함).
> 상세 설계는 [PLAN.md](../PLAN.md), 버전별 변경 이력은 [CHANGELOG.md](CHANGELOG.md),
> 구현은 `src/` 5개 모듈 참조. 139 tests passing (v0.47 기준).
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
| think.py 추출 | actions.py 655→325 LOC (v0.30 import 정리 후 321) | v0.29 |
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
| Skeleton 재검증 3차 | mcp-builder/Best Practices 재대조 신규 위반 0건 — §12.2-3 중복 통합(M0/M1→1건), think.py dead init 제거, README/LOC 스테일 정정 (PLAN §15) | v0.35 |
| TD-10 pyproject 버전 동기화 | `pyproject.toml` 버전 0.30→0.35 인상 + `test_td10_version_matches_document_version` 버전 회귀 가드 추가 | v0.36 |
| CLEAN-3 `_compute_dag_health` 이전 | `think.py` → `actions.py` 이전 — 정의 위치 = 사용 위치 (SRP 준수) | v0.36 |
| TD-9 TypedDict 반환 타입 완비 | `ThinkResult` / `StatusResult` / `InvalidateResult` / `RestoreListResult` / `RestorePayloadResult` / `InfoResult` 6종 정의 | v0.36 |
| TD-11 `context_pressure` 토큰 기반 전환 | `COUNT(COMPLETED)` → `SUM(tokens_original)`, 임계값 900/1700, 반환키 `node_count`→`tokens_original` | v0.37 |
| CLEAN-4 `ThinkResult` TypedDict 정확화 | `total=False` → `total=True` + `parent_context: NotRequired[dict]` — 7개 필수 키 타입체커 정확 보장 | v0.38 |
| DOC-2 `_validate_think_inputs` WHAT 주석 제거 | 함수명·시그니처로 자명 — WHAT 주석 불필요 | v0.38 |
| CLEAN-6 `RestorePayloadResult` TypedDict 정확화 | `total=False` → `total=True` + `warning: NotRequired[str]` — 3개 필수 키 타입체커 정확 보장 | v0.39 |
| CLEAN-7 `compressor.py` WHAT 주석 4건 제거 | `_is_cjk_char` docstring, position bonus 설명 등 — WHY 주석 1건 보존 | v0.39 |
| CLEAN-8 `compressor.py` 스테일 역사 주석 제거 | `ContentRouter 유사` 등 이전 출처 참조 + WHAT 인라인 주석 2건 제거 | v0.40 |
| CLEAN-9 `actions.py` 섹션 헤더 칼러 참조 제거 | `moved from think.py — used only by _action_status` 등 이전 출처 참조 제거 | v0.40 |
| DOC-3 PLAN.md 문서 제목 정정 | `v0.37` → `v0.39` (문서 스테일) | v0.40 |
| CLEAN-10 TypedDict 메타검증 테스트 삭제 | `TestThinkResultTyping`·`TestRestorePayloadResultTyping` — 런타임 행위 아닌 Python 타입 시스템 내부 검사 (132→130 tests) | v0.41 |
| DOC-4 §6 LOC 실측 정정 | `server.py` 210→232, `actions.py` 350→416, `think.py` 266→311, `db.py` 133→152, `compressor.py` 235→274 | v0.41 |
| TD-12 세션 정리 정책 구현 | `cleanup_if_needed` (delete/archive 정책), `get_archive_db_path`, `_run_cleanup` 통합 — 환경변수 기반 자동 실행 (130→139 tests) | v0.42 |
| BUG-2 `cleanup_if_needed` 누락 import | `actions.py`에서 `cleanup_if_needed`가 import 없이 사용 — `except Exception: pass`로 무음 스왈로 되어 cleanup이 실행 안 되던 버그 수정 | v0.43 |
| CLEAN-11 스테일 버전 하한 테스트 삭제 | `test_td10_version_matches_document_version` — `>= (0, 35)` 하한 가드 불필요, `test_info_version_is_dynamic`로 커버 (139→138 tests) | v0.43 |
| CLEAN-12 `note=None` 정규화 버그 수정 | `_action_think`에 `note = "" if note is None else note` 추가 — `_validate_think_inputs`의 지역 정규화가 호출자에게 전파 안 되는 버그. Dead code 제거 + 타입 `str\|None → str` 정확화. `test_note_none_is_tolerated` DB 직접 검증 추가 | v0.44 |
| CLEAN-13 payload 검증 매직넘버 상수화 | `_validate_think_inputs`의 payload 80/1500 bare literal → `_PAYLOAD_MIN_LEN`/`_PAYLOAD_MAX_LEN` (도메인 제약 중 유일한 비명명 리터럴, `_MAX_NODE_NAME_LEN`/`_MAX_NOTE_LEN` 스타일 통일). 에러 메시지 f-string화. hybrid-tdd-architect audit 도출, 행위 불변 | v0.45 |
| CLEAN-14 `restore_cmd` 포맷 중복 제거 (DRY) | `_action_status`/`_action_restore`의 동일 `dag_thinking(action='restore', ...)` f-string 2곳 → `_restore_cmd(session_id, ccr_hash)` 헬퍼로 단일화. `test_restore`가 status 매니페스트와 byte-level 동일 보장(기존 `startswith` → 정확 일치). hybrid-tdd-architect audit 도출, 행위 불변 | v0.46 |
| TD-14 `prepare_release` ruff가 `tests/` 미검사 → 해소 | (v0.46 등재) `check_ruff("src")`만 호출 → tests/ 드리프트(`test_cleanup.py` I001) 축적. (v0.47 해소) `check_ruff(*targets)` 가변 인자화 + `main`이 `src`+`tests` 전달, 기존 드리프트 정리, `test_r4` 회귀 가드 | v0.46→v0.47 |

---

## 검증 상태

- **139 tests passing** (v0.47 기준, 2026-06-13 실측 — 행위 기준 8파일 + tools/eval 보조)
- **line coverage 96%** (v0.45 실측: `pytest --cov=src` — 520 stmts, 22 miss; 미스는 엔트리포인트·방어 분기. v0.46~v0.47은 행위 불변 — 커버리지 영향 없음)
- `prepare_release.py` 6종 체크: source control / LOC limits / static analysis (ruff: src+tests) /
  supply chain audit (pip-audit + SBOM) / test suite / MCP smoke test — 전부 PASS 실측
- 미해소 부채는 PLAN.md §10 참조 (TD-6 배포 시 / 보류: TD-13)
