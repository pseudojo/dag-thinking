# dag-thinking 압축 인지 효용 평가 계획 (TD-13)

> 이 문서는 PLAN.md §10 TD-13의 상세 평가 계획이다.
> 핵심 질문: **CCR 압축된 parent_context로도 원문 수준의 추론 품질을 유지할 수 있는가?**

---

## 1. 가설 (Hypotheses)

| ID | 가설 | 검증 지표 | 합격 기준 |
|----|------|-----------|-----------|
| H1 | CCR 압축된 parent_context를 사용해도 원문 수준의 추론 품질을 달성할 수 있다 | LLM 최종 결론 일치율 | ≥ 90% |
| H2 | 압축 사용 시 세션 토큰 비용이 미사용 대비 의미 있게 감소한다 | total_tokens 절감율 | ≥ 15% |
| H3 | thought_type별 키워드 가중치(_TYPE_KEYWORDS)는 해당 타입 추론 품질 보존에 기여한다 | type-specific 키워드 보존율 차이 | ≥ 5%p 향상 |
| H4 | byte-identical restore(ccr_store)는 압축으로 인한 정보 손실을 완전히 보상한다 | 복원 후 추론 품질 | 원문 수준과 동등 (≥ 99%) |

---

## 2. 평가 방법론

### 2.1 자동화 테스트 (pytest 기반, 의존성 없음)

결정론적이고 재현 가능한 테스트. `tests/eval/` 디렉토리에 배치.

- 압축 전/후 텍스트 비교 (키워드 보존 여부)
- 압축 비율 검증 (_RATIO_TINY/SHORT/LONG 허용 범위)
- 목록/산문 최소 보존 보장 (floor_k=2)
- 세션 메트릭 정확성 (session_total_saved, tokens_compressed)

실행: `.venv/Scripts/python.exe -m pytest tests/eval/ -v`

### 2.2 LLM 연동 테스트 (`eval_harness.py` 기반)

실제 LLM API와 연동하여 추론 흐름을 자동 기록. `tests/eval/eval_harness.py` 사용.

**필요 조건:**
- Anthropic API 키 (`ANTHROPIC_API_KEY` 환경변수)
- 테스트용 LLM: claude-haiku-4-5 (비용 절감)
- 결과 저장: `tests/eval/results/{session_id}_{timestamp}.json`

**A/B 비교 방식:**
동일 추론 태스크를 두 가지 모드로 실행:
- **A**: 압축 활성화 (기본 동작)
- **B**: 압축 비활성화 (payload를 80자 미만으로 설정하거나 passthrough 강제)

두 결과를 LLM-judge가 맹검 평가 (어느 쪽이 압축 사용인지 모르는 상태).

---

## 3. 평가 기준 (50개, 총 500점 만점)

> 각 기준: 0점 = 기준에 부합하지 않음, 10점 = 기준에 매우 부합함

### 범주 A: 키워드·내용 보존 (A01–A10, 100점)

| ID | 기준 | 측정 방법 |
|----|------|-----------|
| A01 | `IMPORTANCE_KEYWORDS`(error/critical/key/conclusion/therefore 등) 포함 문장이 압축 후 보존된다 | 원문 키워드 문장 ↔ 압축 결과 포함 여부 |
| A02 | 수치·임계값("500 connections", "42%", "1700 tokens")이 압축 후 텍스트에 보존된다 | 정규식으로 수치 추출 후 교집합 비율 |
| A03 | 고유명사(시스템명, 함수명, 서비스명)가 압축 후 텍스트에 보존된다 | 명사 목록 추출 후 보존율 |
| A04 | 인과관계 표현(therefore/because/hence/consequently)이 포함된 문장이 우선 보존된다 | 해당 문장 보존 여부 (0/10) |
| A05 | 부정적 발견("not", "fails", "error", "risk")이 포함된 문장이 압축에서 탈락하지 않는다 | 부정 표현 포함 문장 보존 여부 |
| A06 | 핵심 결론(첫 번째 문장 또는 마지막 문장)이 압축 후 반드시 보존된다 | position_bonus 가중치 효과 검증 |
| A07 | `thought_type=Evidence`일 때 `{data/shows/measured/observed/metric/found/test}` 키워드 문장이 우선 보존된다 | Evidence vs. 일반 압축 비교 |
| A08 | `thought_type=Synthesis`일 때 `{conclude/summary/overall/combine/integrate/reconcile}` 키워드 문장이 우선 보존된다 | Synthesis vs. 일반 압축 비교 |
| A09 | 액션 아이템(must/should/implement/deploy/execute/apply)이 포함된 문장이 `Action` 타입 압축에서 보존된다 | Action 타입 키워드 문장 보존율 |
| A10 | 목록 형식 텍스트에서 키워드 점수 상위 아이템이 하위 아이템보다 우선 보존된다 | 점수 순위 vs. 보존 여부 상관관계 |

### 범주 B: 압축 비율 정확성 (B01–B05, 50점)

| ID | 기준 | 측정 방법 |
|----|------|-----------|
| B01 | 100–280자 텍스트가 70% ±5% 범위 내로 압축된다 (`_RATIO_TINY`) | `len(compressed)/len(original)` |
| B02 | 280–700자 텍스트가 58% ±5% 범위 내로 압축된다 (`_RATIO_SHORT`) | 동일 |
| B03 | 700자 이상 텍스트가 42% ±5% 범위 내로 압축된다 (`_RATIO_LONG`) | 동일 |
| B04 | 절약량 <10%인 경우 원문이 그대로 반환된다 (passthrough, `tokens_saved=0`) | `compressed == original` 확인 |
| B05 | 목록/산문 형식 텍스트에서 최소 2개 항목이 항상 보존된다 (`floor_k=2`) | 압축 결과 항목 수 확인 |

### 범주 C: LLM 추론 충실도 (C01–C10, 100점)

| ID | 기준 | 측정 방법 |
|----|------|-----------|
| C01 | 압축된 `Objective` 노드를 `parent_context`로 받은 LLM이 목표를 정확히 재인식한다 | LLM 응답에서 목표 키워드 일치 여부 |
| C02 | 압축된 `Hypothesis` 노드를 `parent_context`로 받은 LLM이 검증 대상 가설을 정확히 재인식한다 | 가설 내용 일치율 |
| C03 | 압축된 `Evidence` 노드를 `parent_context`로 받은 LLM이 근거를 올바른 가설에 귀속시킨다 | 귀속 정확도 (0/10) |
| C04 | 압축된 `Critique` 노드를 `parent_context`로 받은 LLM이 비판 대상 노드를 정확히 식별한다 | 대상 노드명 일치 여부 |
| C05 | 압축된 다중 부모 컨텍스트(`depends_on=[A,B]`)에서 LLM이 각 부모를 독립적으로 인식한다 | 양쪽 부모 내용 모두 언급 여부 |
| C06 | A→B→C 체인에서 B의 압축 `parent_context`가 A의 핵심 결론을 C까지 전달한다 | A의 핵심 결론이 C 응답에 반영되는지 |
| C07 | 압축 컨텍스트만으로 동일 태스크에 대해 원문 수준의 결론에 도달한다 | A/B 결론 일치율 |
| C08 | `INVALIDATED` 부모 경고를 포함한 압축 컨텍스트에서 LLM이 재검토 필요성을 인식한다 | LLM 응답에 재검토 언급 여부 |
| C09 | 압축 컨텍스트에 정보 누락이 발생할 때 LLM이 `ccr_hash`를 통한 원본 복원을 자발적으로 요청한다 | restore 호출 여부 |
| C10 | `restore` 후 원문 컨텍스트로 추론 재개 시 올바른 결론에 도달한다 | 복원 후 결론 품질 |

### 범주 D: 태스크 완성도 (D01–D08, 80점)

| ID | 기준 | 측정 방법 |
|----|------|-----------|
| D01 | 3-노드 세션(Objective→Evidence→Synthesis)이 압축 하에서 성공적으로 완료된다 | Synthesis 노드 생성 성공 여부 |
| D02 | 5-노드 세션이 압축 하에서 논리 일관성을 유지하며 완료된다 | LLM-judge 일관성 평가 |
| D03 | 10-노드 세션이 압축 하에서 전체 추론 체인을 완료한다 | Action 노드 생성 성공 여부 |
| D04 | 분기 DAG(A→B, A→C) 구조에서 압축이 각 분기를 독립적으로 올바르게 처리한다 | 분기별 결론 독립성 확인 |
| D05 | 무효화(`invalidate`) 후 재생성 시나리오가 압축 하에서 올바르게 처리된다 | 재생성 노드 품질 |
| D06 | 한국어 텍스트 압축 후 LLM 추론 품질이 영어 대비 동등 수준(±10%)을 유지한다 | 한/영 품질 점수 차이 |
| D07 | `context_pressure=high`(≥1700 tokens) 조건에서 LLM이 `Synthesis` 방향으로 올바르게 수렴한다 | next_hint 준수 여부 |
| D08 | 최대 depth(5 이상) 체인에서 각 레벨의 압축 컨텍스트가 충분한 정보를 하위로 전달한다 | 최하위 노드에서 최상위 목표 재현율 |

### 범주 E: 토큰 효율성 (E01–E07, 70점)

| ID | 기준 | 측정 방법 |
|----|------|-----------|
| E01 | 압축 사용 시 세션 총 토큰 사용량이 미사용 대비 최소 15% 절감된다 | `(B.total - A.total) / B.total` |
| E02 | 압축 사용 시 LLM 멀티턴 횟수가 미사용 대비 동등하거나 적다 | 턴 수 비교 |
| E03 | `restore` 요청 횟수가 전체 `think` 호출의 20% 미만이다 | `restore_calls / think_calls` |
| E04 | 압축으로 인한 최종 오답 발생률이 전체 평가 케이스의 5% 미만이다 | 오답 케이스 수 / 전체 케이스 수 |
| E05 | `restore` 후 자기 수정 성공률이 90% 이상이다 | 수정 성공 / 전체 restore 수 |
| E06 | `session_total_saved` 반환값이 실제 절감된 토큰과 ±5% 이내로 일치한다 | API usage vs. session_total_saved |
| E07 | 10-노드 세션에서 `tokens_compressed / tokens_original` 비율이 0.5 미만이다 | status() 메트릭 확인 |

### 범주 F: 특수 케이스 (F01–F05, 50점)

| ID | 기준 | 측정 방법 |
|----|------|-----------|
| F01 | 단일 문장 payload(정확히 80–100자)의 압축 후에도 핵심 의미가 보존된다 | 의미 유사도 (LLM-judge) |
| F02 | 한글–영어 혼합 텍스트에서 CJK와 ASCII 양쪽 핵심 내용이 모두 보존된다 | 한/영 키워드 각각 보존 여부 |
| F03 | 줄임표("...")가 포함된 텍스트에서 문장 분리 오류 없이 의미 단위가 유지된다 | 줄임표 경계 분리 여부 |
| F04 | CJK 종결자(。！？)로 끝나는 문장이 포함된 텍스트에서 경계 분리가 정확하다 | 분리 결과 문장 수 |
| F05 | 코드 식별자(함수명, 변수명) 또는 수식이 포함된 텍스트에서 해당 식별자가 보존된다 | 식별자 추출 후 보존율 |

### 범주 G: 시스템 통합 (G01–G05, 50점)

| ID | 기준 | 측정 방법 |
|----|------|-----------|
| G01 | MCP 툴 호출(`dag_thinking`) 응답 시간이 압축 여부와 무관하게 200ms 미만이다 | `time.perf_counter()` 측정 |
| G02 | `ccr_store`에서 복원된 `original_payload`가 `think` 입력 payload와 byte-level 동일하다 | `restored == original` |
| G03 | 동일 세션에서 압축/비압축 노드 혼재 시 `status()` 메트릭이 정확하다 | `tokens_saved` 합산 검증 |
| G04 | 압축된 `parent_context` 포함 `think` 응답 크기가 압축 없는 경우보다 작다 | `len(json.dumps(response))` 비교 |
| G05 | 연속 100회 `think` 호출 시 SQLite 연결 누수나 비정상 종료가 발생하지 않는다 | 예외 없이 완료 + DB 정합성 확인 |

---

## 4. 자동 평가 하네스 (`tests/eval/eval_harness.py`)

실제 LLM과 연동하는 평가 흐름을 자동 기록한다. LLM 클라이언트는 프로토콜로 주입 — 특정 SDK에 의존하지 않음.

```python
# tests/eval/eval_harness.py 사용 예시 (Anthropic SDK 기준)

import anthropic
from tests.eval.eval_harness import EvalHarness

harness = EvalHarness(session_id="eval_h1_001")
client = anthropic.Anthropic()

# 각 턴 기록
response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    tools=[dag_thinking_tool_schema],
    messages=messages,
)
harness.record_turn(
    turn_index=0,
    messages=messages,
    tool_calls=[...],   # response.content에서 tool_use 블록 추출
    tool_results=[...], # dag_thinking 실제 호출 결과
    usage={
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    },
)

# 세션 종료 후 저장
saved_path = harness.save()
print(harness.summary())
# {session_id, total_turns, total_input_tokens, total_output_tokens, total_tokens}
```

저장 파일 위치: `tests/eval/results/eval_{session_id}_{timestamp}.json`
저장 파일은 `.gitignore`에 추가 (API 비용 결과이므로 레포에 포함 안 함).

---

## 5. 합격 기준 및 해석

| 총점 범위 | 등급 | 의미 |
|-----------|------|------|
| 450–500점 | S | 원문 대비 압축 손실 무시 가능, 프로덕션 사용 적합 |
| 400–449점 | A | 대부분 케이스에서 충분한 품질, 경계 케이스 보완 권장 |
| 350–399점 | B | 일부 thought_type 또는 언어에서 품질 저하, 개선 필요 |
| 300–349점 | C | 주요 케이스에서 품질 저하, 압축 알고리즘 재검토 필요 |
| 300점 미만 | F | 압축 기능이 오히려 추론을 방해, 즉시 개선 필요 |

**H1 합격 조건:** C07(압축 결론 일치율) ≥ 9점 AND C-범주 평균 ≥ 8점
**H2 합격 조건:** E01(토큰 절감율 ≥15%) = 10점
**H3 합격 조건:** A07·A08·A09 평균이 A01–A06 평균보다 5%p 이상 높음
**H4 합격 조건:** C10(복원 후 결론 품질) = 10점 AND G02(byte-level 동일) = 10점

---

## 6. 실행 트리거 조건

TD-13 평가는 아래 조건 중 하나가 충족될 때 실행한다:

- 압축 알고리즘(`compressor.py`) 변경 시
- `_RATIO_TINY/SHORT/LONG` 임계값 변경 시
- `_TYPE_KEYWORDS` 업데이트 시
- 신규 모델 배포로 인한 token 특성 변화 시
- 프로덕션 투입 전 최종 검증 시

---

> 관련 파일: `tests/eval/eval_harness.py` (하네스 구현), `tests/eval/results/` (저장 결과, gitignore)
> 관련 PLAN.md 항목: §10 TD-13, §10.1 TD-12
