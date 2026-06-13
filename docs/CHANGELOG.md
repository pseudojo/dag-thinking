# dag-thinking 변경 이력 (Changelog)

> v0.1 ~ v0.45 버전별 전체 이력. 최신 버전이 위에 온다.
> 개선 항목 ID(I/Q/R/P/BUG/SEC/PERF/TYPE/TD 시리즈)별 색인은 [IMPROVEMENTS.md](IMPROVEMENTS.md),
> 설계 배경·스펙·기술 부채 로드맵은 [PLAN.md](../PLAN.md)를 참조하세요.

---

## v0.48 (2026-06-13) — CLEAN-15 · compressor 선택 로직 DRY · 139 tests

- **CLEAN-15** compressor `_compress_list`/`_compress_prose` 선택 알고리즘 중복 제거 (DRY)
  - 두 함수가 동일한 "단위별 중요도 score → 상위 k개(floor 2) → 원문 순서 복원" 로직을 각각 12줄로 보유
  - `_select_top_k(units, target_ratio, extra_keywords) -> list[str]` 헬퍼로 단일화 —
    `_compress_list`는 `"\n".join(...)`, `_compress_prose`는 `_join_sentences(...)`로 결합만 분기
  - 행위 불변 (139 green) — `TestCompressList`(아이템 보존·개수 범위) + `TestCompressProse`(키워드 보존·길이 감소)가 안전망
  - compressor.py 274 LOC 불변 (중복 12줄 ×2 → 헬퍼 1개 + thin caller 2개)
  - REFACTOR — 신규 테스트 없음(사적 헬퍼 직접 테스트는 test-for-test이므로 지양, 기존 행위 테스트로 커버)
  - pyproject 버전 0.45 유지 (MCP 서버 연결 중)

---

## v0.47 (2026-06-13) — TD-14 · 릴리스 게이트 tests/ 린트 확장 · 139 tests

- **TD-14** `prepare_release` 정적 분석(§4.2-3)이 `tests/`에 미적용이던 갭 해소
  - `check_ruff(src_dir)` → `check_ruff(*targets)` 가변 인자화, `main()`이 `src`+`tests` 두 경로 전달
    (`"static analysis (ruff: src + tests)"`) — 게이트는 여전히 6종(PASS 카운트 불변)
  - 기존 tests/ 드리프트 일괄 정리: `test_cleanup.py` I001(임포트 정렬) + `test_cleanup.py`/`test_dispatcher.py` 포맷
  - `test_r4_lints_src_and_tests` 추가 — 다중 타겟이 ruff cmd에 모두 전달되는지 회귀 가드 (138→139)
  - `_patch_all_pass`의 `check_ruff` 모킹을 `lambda *targets`로 갱신 (신규 호출 시그니처 정합)
  - pyproject 버전 0.45 유지 (MCP 서버 연결 중 — editable 재설치 차단)

---

## v0.46 (2026-06-13) — CLEAN-14 · hybrid-tdd-architect 재감사 · 138 tests

- **CLEAN-14** `actions.py` restore_cmd 포맷 중복 제거 (DRY)
  - `_action_status`(restoration_manifest)와 `_action_restore`(restorable_nodes)가 동일한
    `f"dag_thinking(action='restore', session_id=..., ccr_hash=...)"` f-string을 각각 보유
  - `_restore_cmd(session_id, ccr_hash) -> str` 헬퍼로 단일화 — 두 경로가 byte-level 동일 보장
  - `test_restore::test_no_hash_lists_restorable_nodes` 강화: restore 목록의 restore_cmd가 status
    매니페스트와 정확히 일치하는지 명시 (기존 `startswith`만 검사 → 정확 일치)
  - 행위 불변 (138 green) — REFACTOR (테스트 선강화 → 헬퍼 추출 순)
- **아키텍처 재감사** (hybrid-tdd-lifecycle-architect + mcp-builder)
  - tests-for-tests 0건 — 메타 테스트는 v0.19/v0.20/v0.23/v0.41에서 이미 소거, 현 스위트는 전부 공개 API 행위 검증
  - mcp-builder 품질 체크리스트 신규 위반 0건 (단일 툴 / annotations / TypedDict 출력 / Resource / info 진단 / ToolError isError 모두 충족)
  - **TD-14 신규**: `prepare_release.check_ruff`가 `src`만 린트 → `tests/`에 임포트 정렬 드리프트(`test_cleanup.py` I001) 축적
  - pyproject 버전 0.45 유지: MCP 서버 연결 중 editable 재설치(잠긴 exe) 차단 — 차기 서버 재기동 시 인상

---

## v0.45 (2026-06-13) — CLEAN-13 · hybrid-tdd-architect audit · 138 tests

- **CLEAN-13** `think.py` payload 검증 매직넘버 → 명명 상수
  - `_validate_think_inputs`의 payload 길이 검증(`< 80`, `> 1500`)이 도메인 제약 중 유일한 bare literal
    (`node_name`/`note`/`depends_on`/`session_id`은 모두 `_MAX_*` 명명 상수 사용)
  - `_PAYLOAD_MIN_LEN = 80` / `_PAYLOAD_MAX_LEN = 1500` 추출, 에러 메시지 f-string화 (값 단일 소스)
  - 행위 불변 (138 green) — `test_payload_79/80/1500/1501`이 안전망
- **아키텍처 감사** (hybrid-tdd-lifecycle-architect)
  - line coverage 96% (520 stmts, 22 miss — 미스는 `server.py` main/resource 엔트리·방어 분기)
  - Test-to-Code ~0.79:1 (deep modules — 96% 커버리지가 충분성 입증, "저비율=과소테스트" 가설 반증)
  - Boundary Regression Index ~2 (이중 계층 검증: Pydantic 스키마 + 도메인, < 5 = 비치명적) → PLAN.md §9.3 등재

---

## v0.44 (2026-06-13) — CLEAN-12 · 138 tests

- **CLEAN-12** `think.py:_action_think` `note=None` 정규화 버그 수정
  - `_validate_think_inputs`에서 `note`를 지역 변수로 정규화하던 방식은 호출자에게 전파되지 않아
    `note=None` 입력 시 DB `note` 컬럼에 `""` 대신 `NULL`이 저장되던 버그
  - `_action_think` 진입 시 `if note is None: note = ""` 추가
  - `_validate_think_inputs`의 dead code(`if note is None: note = ""`) 제거 + 타입 `str | None → str` 정확화
  - 기회 수정: `actions.py:362` E501 (cleanup_if_needed 호출 줄 래핑)
  - `test_note_none_is_tolerated` 강화 — DB 직접 조회로 `row["note"] == ""` 검증 추가
  - 138 tests (변경 없음)

---

## v0.43 (2026-06-13) — BUG-2 · CLEAN-11 · 138 tests

- **BUG-2** `actions.py`에서 `cleanup_if_needed` import 누락 수정
  - `_run_cleanup` 헬퍼가 `except Exception: pass`로 `NameError`를 삼켜 TD-12 클린업이 실제로 실행되지 않던 버그
  - `from .db import (...)` 블록에 `cleanup_if_needed` 추가
- **CLEAN-11** `test_dispatcher.py`에서 스테일 버전 비교 테스트 삭제
  - `test_td10_version_matches_document_version`: v0.35에서 `pyproject.toml` 버전 플로어 `>= (0, 35)` 검증용으로 작성됐으나 현재 버전에서 항상 참 → 의미 없음
  - 행위(dynamic version reading)는 `test_info_version_is_dynamic`이 이미 커버
  - 139 → 138 tests

---

## v0.42 (2026-06-13) — TD-12 · 139 tests

- **TD-12** 세션 만료/최대 수 정책 구현 (`cleanup_if_needed`)
  - `src/db.py`: `cleanup_if_needed`, `get_archive_db_path`, `_get_cleanup_candidates`, `_delete_sessions`, `_archive_sessions` 추가
  - `src/actions.py`: `_run_cleanup` 헬퍼 추가, `think`/`status` 액션 진입 시 자동 실행
  - 환경 변수: `DAG_SESSION_MAX_AGE_DAYS` (기본 30), `DAG_SESSION_MAX_COUNT` (기본 500), `DAG_CLEANUP_POLICY` (기본 `delete`, 또는 `archive`)
  - `archive` 정책: 주 DB에서 제거 전 `dag-thinking-archive-YYYYMMDD.db`로 세션·노드·ccr_store 전체 복사
  - 현재 `session_id`는 age/count 초과 여부와 무관하게 항상 보호
  - 실패 시 silent (MCP 툴 응답에 영향 없음)
  - `tests/test_cleanup.py` 신설: T-CL01 ~ T-CL07 (9 tests), 130 → 139 tests

---

## v0.41 (2026-06-13) — CLEAN-10 · DOC-4 · 130 tests

- **CLEAN-10** `test_dispatcher.py` TypedDict 메타검증 테스트 2건 삭제: `TestThinkResultTyping`·`TestRestorePayloadResultTyping`
  - 이 테스트들은 `TypedDict.__required_keys__`·`__optional_keys__` Python 타입 시스템 내부를 검사 — 런타임 MCP 행위와 무관
  - 행위(parent_context 선택적 포함, warning 선택적 포함)는 `TestParentContext`·`TestRestoreWarnings`가 이미 커버
  - 132 → 130 tests
- **DOC-4** PLAN.md §6 LOC 실측 정정 (v0.35 실측 이후 v0.36~v0.40 코드 변동으로 스테일)
  - `server.py` 210 → 232 LOC
  - `actions.py` 350 → 416 LOC (`_compute_dag_health` CLEAN-3 이전 등)
  - `think.py` 266 → 311 LOC (ThinkResult TypedDict, _compute_context_pressure 등)
  - `db.py` 133 → 152 LOC
  - `compressor.py` 235 → 274 LOC

## v0.40 (2026-06-13) — 주석·문서 정리 (코드 불변) · 132 tests

- **CLEAN-8** `compressor.py` 스테일 역사 주석(`ContentRouter 유사`) 및 WHAT 인라인 주석 2건 추가 제거
- **CLEAN-9** `actions.py` 섹션 헤더에서 이전 출처 칼러 참조 제거 (`moved from think.py — used only by _action_status`)
- **DOC-3** PLAN.md 문서 제목 `v0.37` → `v0.39` 정정

## v0.39 (2026-06-13) — CLEAN-6 · CLEAN-7 · 132 tests

- **CLEAN-6** `RestorePayloadResult(TypedDict, total=False)` → `TypedDict`(total=True) + `warning: NotRequired[str]` — `node_name`·`original_payload`·`tokens` 3개 키 필수 정확화
- **CLEAN-7** `compressor.py` WHAT 주석 4건 제거 (`_is_cjk_char` docstring, position bonus 설명, 가중치 변수명 설명, threshold 조건식 설명); WHY 주석 보존: `# \b\w+\b collapses an entire CJK run to one "word" — use char count instead`

## v0.38 (2026-06-13) — CLEAN-4 · DOC-2 · 131 tests

- **CLEAN-4** `ThinkResult(TypedDict, total=False)` → `TypedDict`(total=True) + `parent_context: NotRequired[dict]` — 7개 필수 키 타입체커 정확 인식
- **DOC-2** `_validate_think_inputs` WHAT docstring 제거 (함수명·시그니처로 자명)

## v0.37 (2026-06-13) — TD-11 해소 · 130 tests

- **TD-11** `context_pressure` 압박 신호 전환: `COUNT(COMPLETED)` 노드 수 → `SUM(tokens_original)` 토큰 누적합
- 임계값: `_PRESSURE_MEDIUM_TOKENS=900`, `_PRESSURE_HIGH_TOKENS=1700` (구 8/15 노드 기준 행위 보존)
- 반환 키 `node_count` → `tokens_original`, 힌트 문구 "X nodes" → "accumulated X tokens"
- `TestContextPressure` 4건 교체 (node_count 기반 → tokens_original 기반)

## v0.36 (2026-06-13) — TD-9 · TD-10 · CLEAN-3 해소 · 130 tests

- **TD-10** `pyproject.toml` 버전 `0.30` → `0.35` 인상 + `test_td10_version_matches_document_version` 추가 (버전 회귀 가드)
- **CLEAN-3** `_compute_dag_health` `think.py` → `actions.py` 이전 — SRP 준수 (정의 위치 = 사용 위치)
- **TD-9** TypedDict 반환 타입 완비 — `ThinkResult`(think.py) + `StatusResult`/`InvalidateResult`/`RestoreListResult`/`RestorePayloadResult`/`InfoResult`(actions.py)

## v0.35 (2026-06-13) — Skeleton 재검증 3차 · 129 tests

- mcp-builder 스킬 + MCP Best Practices 전면 재대조 — **신규 표준 위반 0건** (PLAN.md §15)
- 테스트를 위한 테스트 재감사 — §12.2-3 중복 1건 통합(prepare_release M0/M1 → 1건, 130→129 tests)
- 소스 스켈레톤 정리 — `think.py` dead init(`delta=0`) 제거 (동작 불변)
- 문서 스테일 정정 — README 폐기 경로(`test_server.py`) 교정, PLAN §6 LOC 실측 동기화

## v0.34 (2026-06-12) — 외부 리뷰 triage (문서 리비전) · 130 tests

- 외부 리뷰 4종 판정 (PLAN.md §14) — `context_pressure` 토큰 기반 전환(TD-11, 차기 최우선) 등 부채 3건 등재, TD-9 재평가
- 포지셔닝 명문화: sequential-thinking의 **대체재가 아닌 보완재** — 노드 내부 추론 강제는 sequential-thinking, 세션 토폴로지·컨텍스트 관리(CCR)는 dag-thinking (병행 권장)
- `ccr_hash` 알고리즘 리뷰 — xxHash·uuid·Ed25519 등 대안 전수 실측 후 현행 `sha256[:24]` 유지 판정 (PLAN.md §14.4)

## v0.33 (2026-06-12) — 공급망 검증 (TD-8 해소) · 130 tests

- `prepare_release.py`에 `check_audit` 추가 — `uvx pip-audit` 취약점 감사 + CycloneDX SBOM 생성 (§4.2-2), 6종 체크 완성
- 프로젝트 의존성 불변 (`uvx` 격리 실행 — Lightweight 원칙 유지)
- §12.2-1 위반 메타 테스트 재유입 2건 삭제(L5/R4) + 소스 스켈레톤 정리

## v0.32 (2026-06-12) — Skeleton 재구성 (TDD) · 128 tests

- 테스트 스위트를 버전 이력 기준 31파일(459 tests)에서 **행위 기준 8파일(128 tests)**로 재구성
- 테스트를 위한 테스트 삭제 — 메타(ruff subprocess), 구현 세부(인덱스 존재·리네임 가드), 중복, 백컴팻 경유
- `__all__` 재수출 제거 (TD-3 해소) — 테스트가 실제 정의 모듈에서 직접 import
- `prepare_release.py`에 `check_ruff` 추가 — §4.2-3 정적 분석, 5종 체크 완성

## v0.31 (2026-06-12) — MCP 표준 재리뷰 (문서 리비전) · 459 tests

- mcp-builder 스킬 + MCP Best Practices 문서 전면 대조 리뷰 — 준수 현황 PLAN.md §9 갱신
- docs/IMPROVEMENTS.md 전면 갱신 (미등재 시리즈 P/BUG/R/STYLE/QUAL 등재, TD-2 해소)
- 잔여 부채: 공급망 감사+SBOM(TD-8), outputSchema(TD-9), Docker(TD-6), `__all__` 정리(TD-3)

## v0.30 — MCP 표준 에러 / 릴리스 검증 · 459 tests

- **TD-5** MCP 표준 에러 — `ValueError` → `raise ToolError` → protocol-level isError 변환
- **TD-7** `prepare_release.py` 신설 — §4.2 릴리스 검증 파이프라인 (git/LOC/tests/smoke 4종)
- **TD-4** import fallback 제거 — `.compressor` 단일 relative import
- **TD-1** 테스트 파일명 교정 — `test_i11_i12.py` → `test_restore_list_health.py`

## v0.29 — Post-review 수정 · 443 tests

- `think.py` 추출 — actions.py 655→325 LOC (<500 LOC 준수)
- `_action_info` 동적 버전 (importlib.metadata), `session_id` min_length 제거
- compressor.py 마커 회귀 수정, 테스트 미사용 import 제거

## v0.28 — MCP Best Practices §2.2/§3.2/§4.2 · 437 tests

- 3-file split: db.py + actions.py + server.py (<500 LOC/파일)
- `action='info'` 진단 엔드포인트 (§3.2), XML 시맨틱 태그 instructions (§2.2)

## v0.27 — Skeleton Refactor · 431 tests

- version-tracking comment 제거, FastMCP instructions 추가 (MCP discoverability)

## v0.26 — MCP Resource · 430 tests

- MCP Resource `dag-thinking-session://{session_id}` 등록
- `_cascade_invalidate` forward_graph 명칭 개선

## v0.25 — MCP 프로토콜 표준 준수 · 427 tests

- `dag_thinking` async + error handling(isError), 서버명 `dag_thinking_mcp`
- `_split_sentences` null byte(`\x00`) 처리

## v0.24 — 스키마 마무리 · 422 tests

- CLAUDE.md/Hook 환경설정 + `target_node` maxLength=200, `payload` min/maxLength=80/1500 MCP schema

## v0.23 — 제약 강화 · 417 tests

- 불필요한 테스트 제거(inspect.getsource 기반 R2-T5/R3-T5) + `node_name`/`reason` Field max_length

## v0.22 — docstring 예시 · 415 tests

- 중복 제거(test_v12 I28 x2, test_v10 I20 x3) + docstring "Use when:/Don't use when:" 예시

## v0.21 — Field 제약 · 416 tests

- 중복 제거(test_i09_i10 T9/T10) + Field 제약(`session_id` min/maxLength=1/200, `note` maxLength=500)

## v0.20 — 스키마 풍부화

- 중복 테스트 제거(IC27/IC28/IC29) + MCP inputSchema Field descriptions(10개 파라미터 전체)

## v0.19 — MCP 표준화

- 중복 테스트 14건 제거 + MCP ToolAnnotations(readOnlyHint/destructiveHint/idempotentHint/openWorldHint)

## v0.18 — 성능·안전성·경고 (I49~I53)

- **I49** `_split_sentences` 약어 false-split 방지(Mr./Dr. 등), **I50** cycle check 트랜잭션 내부 이동
- **I51** `node_name` 공백 정규화(strip), **I52** 복원 시 삭제 노드 warning, **I53** `_cascade_invalidate` BFS 개선

## v0.17 — 입력 방어 보강 (I46~I48)

- **I46** `note=None` 방어(None→"" 변환), **I47** `target_node` 공백 정규화(strip)
- **I48** `_split_sentences` 복합 종결자(?.!/!? 등) 지원

## v0.16 — 응답 풍부화 / 압축 정확성 (I42~I45)

- **I42** think 응답 `thought_type` 필드 추가, **I43** status `dag.nodes` `ccr_hash` 필드 추가
- **I44** `_is_list_content` `+` 불릿 지원(GFM), **I45** `_compute_dag_health` `total_nodes` 카운트 추가

## v0.15 — 압축 정확성 / 성능 / 입력 방어 (I38~I41)

- **I38** `_split_sentences` 줄임표+공백 false-split 수정(2-char lookbehind), **I39** `_compress_prose` 최소 k=2
- **I40** `depends_on` 빈 경우 cycle check 스킵, **I41** `_action_invalidate` target_node 공백 전용 방어

## v0.14 — PERF-2 완성 / 입력 방어 / 압축 품질 (I35~I37)

- **I35** `_action_think` PERF-2 완성(읽기 쿼리 트랜잭션 외부), **I36** `note` 길이 상한(`_MAX_NOTE_LEN=500`)
- **I37** `_compress_list` 최소 k=2

## v0.13 — 입력 방어 / 인덱스 / 알고리즘 수정 (I31~I34)

- **I31** 공백 전용 payload 차단, **I32** `idx_edges_child` 인덱스 추가
- **I33** `_split_sentences` 줄임표 false-split 수정, **I34** edges 루프→executemany+가드 정리

## v0.12 — DRY / 쿼리 최적화 / 입력 방어 · 282 tests

- **I25** `_is_cjk_char()` 헬퍼 추출 — `estimate_tokens`와 `_score_sentence` CJK 범위 정의 통일 (DRY)
- **I28** `_action_restore()` ccr_store+nodes 2-query → LEFT JOIN 1-query 통합
- **I29** `call_dag_thinking()` `depends_on` 중복 항목 순서 보존 제거
- **I30** `call_dag_thinking()` `session_id` 길이 상한 `_MAX_SESSION_ID_LEN=200` 추가

## v0.11 (2026-06-10) — 트랜잭션 최적화 / CJK 안전성 / 스코어링 개선 · 247 tests

ruthless-code-critic 감사 기반 TDD 개선:

- **I20** `session_total_saved` SELECT 트랜잭션 외부 이동 — PERF-2 원칙 완성. `_action_think`의 `with conn:` 블록 내에서 `UPDATE sessions` 이후 `SELECT tokens_saved`를 실행해 쓰기 락을 불필요하게 연장하던 구조 수정. `prev_session_total`을 `with conn:` 이전에 읽고 `session_total_saved = prev_session_total + delta`로 로컬 계산 교체
- **I23** CJK Compatibility Ideographs 유니코드 이스케이프 교체 — `estimate_tokens()`의 리터럴 범위 경계 문자를 유니코드 이스케이프로 교체. 소스 파일 인코딩 훼손 시 범위 경계 문자가 깨져 CJK 토큰 계산이 오작동할 위험 제거
- **I24** `_score_sentence()` CJK-aware word_count — `re.findall(r"\b\w+\b")`가 CJK 연속 문자를 하나의 토큰으로 처리해 `word_count=1 < 5` → 전 CJK 문장에 균일 `-0.5` 패널티 부여하던 버그 수정. CJK 문자 비율 > 50% 시 CJK 문자 수를 `word_count` 대리값으로 사용, 짧은/긴 CJK 문장을 정확히 구분

## v0.10 (2026-06-10) — 압축 품질 / 토큰 정확도 / 입력 방어 · 231 tests

ruthless-code-critic 감사 기반 TDD 개선:

- **I21** `_join_sentences()` 추출 + `_compress_prose()` CJK 재결합 수정 — v0.9에서 CJK 문장 분리를 추가했으나 재결합은 여전히 `" ".join()` 사용. `"A。B。C。"` 압축 시 `"A。 B。 C。"` (원문에 없는 공백 삽입) 버그 수정. `_CJK_TERMINATORS = frozenset("。！？")`으로 종결자 감지 후 CJK 문장은 공백 없이, ASCII 문장은 공백으로 구분 결합
- **I18** `estimate_tokens()` CJK 확장 범위 보완 — CJK Extension A (U+3400~U+4DBF, ~6,600자), CJK Compatibility Ideographs (U+F900~U+FAFF), CJK Extension B+ SMP (`ord(ch) >= 0x20000`) 미처리 문자들을 `non_cjk`(÷4)로 계산해 토큰 수 최대 8배 과소 산출하던 버그 수정
- **I20** `session_total_saved` 회귀 안전성 — 기존 누적 계산 정확성 검증 테스트 3건 추가
- **I22** `_validate_think_inputs()` `node_name` 길이 상한 — 무제한 길이 `node_name`으로 인한 잠재적 DoS 및 SQL 인덱스 비효율 차단. `_MAX_NODE_NAME_LEN = 200` 상수 도입, blank 검증 직후 길이 검증 실행

## v0.9 (2026-06-10) — 압축 정확성 / 입력 방어 · 208 tests

ruthless-code-critic 감사 기반 TDD 개선:

- **I12** `_split_sentences()` CJK 공백 없는 분리 — `r"(?<=[.!?。！？])\s+"` 패턴이 CJK 종결자 뒤 공백을 요구해 `"A。B。"` 형태를 1개 문장으로 처리하던 버그 수정. `r"(?<=[.!?])\s+|(?<=[。！？])"` 로 교정 — ASCII는 공백 필요, CJK는 종결자 자체로 즉시 분리
- **I13** `_is_list_content()` middle dot 오탐 제거 — `·` (U+00B7)이 한국어 단어 구분자나 수학 점곱으로 사용되는 텍스트를 목록으로 오분류하던 문제. bullet 패턴에서 U+00B7 제거, `•` (U+2022)만 허용
- **I17** `_validate_think_inputs()` `depends_on` 길이 상한 — `_resolve_parent_context`의 `IN (?, ...)` 파라미터가 SQLite 제한(999)을 초과할 수 있던 잠재적 `OperationalError`. `_MAX_DEPENDS_ON = 20` 상수 도입, 초과 시 즉시 `ValueError` 발생

## v0.8 (2026-06-10) — 버그 수정 / 압축 품질 · 194 tests

ruthless-code-critic 감사 기반 TDD 개선:

- **I09** `_compute_context_pressure()` 쓰기 트랜잭션 밖으로 이동 — `_action_think`의 PERF-2 원칙 완성. `with conn:` 블록 내에 남아있던 COUNT 읽기 쿼리를 커밋 후 실행으로 교정
- **I10** `_compute_dag_health()` INVALIDATED 엣지 BFS 제외 — INVALIDATED 노드와 연결된 엣지가 `max_depth` / `orphan_nodes` 계산을 오염하는 버그 수정. COMPLETED 전용 서브그래프(양쪽 모두 COMPLETED인 엣지)만 사용
- **I11** `_split_sentences()` 함수 추출 + 유니코드 문장 구분자 지원 — `_compress_prose` 내 인라인 분리 로직을 독립 함수로 추출. `r"(?<=[.!?。！？])\s+"` 패턴으로 한중일 구두점(。！？) 지원 추가

## v0.7 (2026-06-09) — 성능 / 보안 / 타입 안전성 · 181 tests

ruthless-code-critic 감사 기반 TDD 개선:

- **SEC-1** 세션 ID 정보 노출 차단 — `_action_restore`에서 타 세션 hash 조회 시 다른 세션의 ID를 에러 메시지에 포함하던 probe 쿼리 제거. `"Hash '...' not found in session '...'"` 형태로 통일
- **PERF-1** `compress()` / `estimate_tokens()` DB 쓰기 락 밖으로 이동 — `_action_think`의 SHA-256 + 문장 스코어링 연산이 SQLite 쓰기 락을 불필요하게 점유하던 문제 해결
- **PERF-2** `_action_status` / `_action_restore` 트랜잭션 범위 최소화 — `_ensure_session` 쓰기 1회만 `with conn:` 안에서 실행, 모든 읽기 쿼리를 트랜잭션 밖으로 이동
- **TYPE-1** 타입 어노테이션 완성 — `_db() -> sqlite3.Connection`, `_compute_dag_health(node_rows: list[sqlite3.Row], edge_rows: list[sqlite3.Row])` 파라미터 타입 추가

## v0.6 (2026-06-09) — 버그 수정 / 구조 정리 · 173 tests

ruthless-code-critic 감사 기반 TDD 개선:

- **R-EDGE** 엣지 삭제 방향 버그 수정 — 노드 upsert 시 `DELETE WHERE parent=?` → `WHERE child=?`. 기존 코드는 노드를 업데이트할 때 자신의 자식 노드들의 부모 관계를 파괴해 cascade invalidate 경로를 끊는 버그가 있었음
- **R-CCR** `ccr_store` 복합 PK 도입 — `hash TEXT PRIMARY KEY` → `PRIMARY KEY (hash, session_id)`. 두 세션이 동일 내용의 노드를 가질 때 `INSERT OR REPLACE`가 session_id를 덮어써서 한 세션의 restore를 파괴하는 충돌 버그 수정
- **R-CCR** `INSERT OR REPLACE` → `INSERT OR IGNORE` + 고아 DELETE 제거 — 업데이트 시 기존 ccr 원본을 삭제하지 않아 content-addressed 보존 원칙 준수
- **CLEAN-1** `_has_cycle()` 데드 코드 30줄 삭제 — v0.5 Q-2 리팩토링 이후 호출처 없는 함수
- **CLEAN-2** 모듈 상수 순서 정규화 — `VALID_THOUGHT_TYPES`, `_PRESSURE_*`, `_NEXT_HINTS`를 첫 사용 함수 이전으로 이동

## v0.5 (2026-06-09) — 내부 품질 개선 · 165 tests

ruthless-code-critic 감사 기반 TDD 개선:

- **Q-1** `session_total_saved` 공식 버그 수정 — 노드 업데이트 시 `delta = new_saved − old_saved` (기존: `old_compressed` 기준으로 오차 발생)
- **Q-2** edge 배치 조회 분리 — `_load_forward_edges` / `_has_cycle_graph` 신규 함수로 cycle check 루프의 N×DB 쿼리 → 1×DB 쿼리로 개선
- **Q-3** SRP 적용 — `_validate_think_inputs` 독립 함수 추출, `_action_think` 책임 축소
- **Q-4** import 가드 수정 — `from compressor import` → `from src.compressor import` (내부 ImportError 노출 방지)
- **Q-5** dead fallback 제거 — `_NEXT_HINTS.get(thought_type, ...)` → `_NEXT_HINTS[thought_type]`
- **Q-6** 스테일 주석 제거 — 태스크 트래킹 주석(`YELLOW_3`, `stub`) 완전 제거

## v0.4 — I06/I07/I08

- thought_type 키워드 가중치(`_TYPE_KEYWORDS`), `context_pressure` 경보, `dag_health` 수렴 진단

## v0.3 — I03/I04/I05

- invalidate 존재 검증, `created_at` 노출, `next_hint` 동적화

## v0.2 — 통합 설계

- 툴 5개 → **1개** (`dag_thinking(action=...)`), 자동 resolve(`depends_on` → parent_context), 복원 매니페스트

## v0.1 — 초기 설계

- 툴 5개 구조 (`think`, `resolve`, `retrieve`, `invalidate`, `status`)
