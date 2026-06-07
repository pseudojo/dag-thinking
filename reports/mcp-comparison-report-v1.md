# MCP 서버 비교 분석 보고서 — dag-headroom vs headroom vs sequential-thinking

> 작성일: 2026-06-07  
> 분석 대상: test-3 (dag-headroom), test-4 (headroom), test-5 (sequential-thinking)  
> 공통 작업: Django vs Spring Framework Deep Dive 보고서 작성  
> **분석 방법**: 생성된 3개 보고서 파일 직접 정독 + 실행 로그(test-*.txt) 분석

---

## 목차

1. [실험 개요](#1-실험-개요)
2. [MCP 서버별 특성 요약](#2-mcp-서버별-특성-요약)
3. [툴 호출 횟수 및 패턴 분석](#3-툴-호출-횟수-및-패턴-분석)
4. [컨텍스트 토큰 사용량 분석](#4-컨텍스트-토큰-사용량-분석)
5. [압축 효율 및 비용 분석](#5-압축-효율-및-비용-분석)
6. [생성 결과물 품질 비교 — 실제 파일 기반](#6-생성-결과물-품질-비교--실제-파일-기반)
7. [MCP 툴 스키마 오버헤드 비교](#7-mcp-툴-스키마-오버헤드-비교)
8. [종합 비교표](#8-종합-비교표)
9. [결론 및 선택 가이드](#9-결론-및-선택-가이드)

---

## 1. 실험 개요

동일한 작업("Django vs Spring Framework Deep Dive 보고서 작성 후 markdown 저장")을 세 가지 MCP 서버로 각각 수행하고, 실행 방식·토큰 소비·비용·결과물 품질을 비교한다.

| 구분 | test-3 | test-4 | test-5 |
|------|--------|--------|--------|
| **사용 MCP 서버** | dag-headroom | headroom | sequential-thinking |
| **핵심 툴** | `mcp__dag-headroom__dag_headroom` | `mcp__headroom__headroom_compress/retrieve/stats` | `mcp__sequential-thinking__sequentialthinking` |
| **생성 파일** | django_vs_spring_v3.md | django-spring-comparison-v1.md | django-spring-deep-dive-v1.md |

---

## 2. MCP 서버별 특성 요약

### 2.1 dag-headroom (test-3)

**동작 원리**: 작업을 DAG(Directed Acyclic Graph) 노드로 구조화. 각 노드는 Objective/Evidence/Critique/Synthesis 등 사고 유형을 가지며, 노드 간 의존성이 방향성 엣지로 표현된다. 완료된 노드 페이로드는 CCR(Contextual Compression Ratio) 해시로 압축 저장된다.

```
[Objective] objective
      ├──→ [Evidence] django_profile
      │         └──→ [Critique] differences
      │                   └──→ [Synthesis] synthesis
      └──→ [Evidence] spring_profile
                └──→ [Critique] differences (동일)
```

**특징**:
- 구조화된 분석 프로세스 — 사고 유형 강제로 논리적 흐름 보장
- DAG 토폴로지로 병렬 브랜치 가능 (django_profile, spring_profile 동시 진행)
- 각 노드의 중간 페이로드를 해시로 압축 (복원 가능)
- `action` 파라미터로 `add_node`, `complete_node`, `status`, `restore` 등 다양한 작업 지원

### 2.2 headroom (test-4)

**동작 원리**: 범용 컨텍스트 압축 저장소. 임의의 텍스트를 압축해 해시로 저장하고, 필요시 복원한다. 사고 구조를 강제하지 않고 압축/복원에만 집중한다.

**3가지 툴**:
- `headroom_compress`: 텍스트 → 압축 + 해시 저장
- `headroom_retrieve`: 해시 → 원본 텍스트 복원
- `headroom_stats`: 세션 압축 통계 조회

**특징**:
- 전략 기반 압축 (`router:mixed:0.53` — 내용에 따라 요약/요약+코드블록 혼합)
- 서브 에이전트 포함 통합 통계 제공
- 비용 절감액($) 측정 가능
- 사고 구조 없음 — 압축 시점/방식은 모델이 자유 결정

### 2.3 sequential-thinking (test-5)

**동작 원리**: 단계별 순차 사고(Chain-of-Thought). `thought`, `thoughtNumber`, `totalThoughts`, `nextThoughtNeeded` 파라미터로 사고 단계를 진행하며, 필요시 분기(branch)나 재검토(isRevision)도 지원한다.

**특징**:
- 선형적 사고 흐름 (기본값)
- 분기/재검토로 유연한 탐색 가능 (이번 실험에서는 사용 안 됨)
- 압축 없음 — 모든 사고 내용이 컨텍스트에 누적
- 가장 자연스러운 단계별 작업 분해

---

## 3. 툴 호출 횟수 및 패턴 분석

### 3.1 툴 호출 횟수

| 툴 종류 | test-3 (dag-headroom) | test-4 (headroom) | test-5 (sequential-thinking) |
|---------|----------------------|-------------------|------------------------------|
| **파일 탐색 (Glob/Read)** | 1회 | 2회 | 2회 |
| **ToolSearch** | 0회 | 1회 | 1회 |
| **핵심 MCP 툴** | ~5회 (dag_headroom) | 2회 (compress 1 + stats 1) | 8회 (sequentialthinking) |
| **파일 쓰기 (Write)** | 1회 | 1회 | 1회 |
| **합계** | **~7회** | **~6회** | **~12회** |

### 3.2 핵심 MCP 툴 호출 상세

**test-3 (dag-headroom)** — 5회 호출 추정:
```
1. add_node: objective (Objective 유형)
2. add_node: django_profile (Evidence 유형)
3. add_node: spring_profile (Evidence 유형)
4. add_node: differences (Critique 유형)
5. add_node/complete + status: synthesis (Synthesis 유형)
```

**test-4 (headroom)** — 2회 호출:
```
1. headroom_compress: 보고서 전체 텍스트 압축 (4,408토큰 → 2,827토큰)
2. headroom_stats: 세션 통계 조회
```

**test-5 (sequential-thinking)** — 8회 호출:
```
1. thought 1: 분석 계획 수립
2. thought 2: Django 핵심 특성 분석
3. thought 3: Spring 핵심 특성 분석
4. thought 4: 기능별 세부 비교
5. thought 5: 성능/확장성/생태계 분석
6. thought 6: 장단점 및 사용 사례 정리
7. thought 7: 비교 표 설계 + 파일명 결정
8. thought 8: 최종 검토 → nextThoughtNeeded: false
```

### 3.3 패턴 특성 비교

```
dag-headroom:   [구조화] 노드 추가 → 노드 완료 → DAG 확장 (병렬 가능)
headroom:       [단순]   보고서 작성 → 완성 후 한 번 압축
sequential:     [순차]   계획 → 분석 → 분석 → 비교 → 정리 → 설계 → 검토 → 완료
```

---

## 4. 컨텍스트 토큰 사용량 분석

### 4.1 컨텍스트 변화 추이

| 측정 시점 | test-3 (dag-headroom) | test-4 (headroom) | test-5 (sequential-thinking) |
|-----------|----------------------|-------------------|------------------------------|
| **작업 시작 전** | 21.9k / 200k (11%) | 22.0k / 200k (11%) | 21.9k / 200k (11%) |
| **작업 완료 후** | 44.8k / 200k (22%) | 56.3k / 200k (28%) | 49.4k / 200k (25%) |
| **총 증가량** | **+22.9k 토큰** | **+34.3k 토큰** | **+27.5k 토큰** |
| **Free space (완료 후)** | 121.8k (60.9%) | 110.3k (55.1%) | 117.1k (58.6%) |

### 4.2 완료 시점 컨텍스트 구성 (Messages 기준)

| 항목 | test-3 (dag-headroom) | test-4 (headroom) | test-5 (sequential-thinking) |
|------|----------------------|-------------------|------------------------------|
| **Messages** | 22.9k (11.5%) | **34.5k (17.3%)** | 27.1k (13.6%) |
| **MCP tools (active)** | 1.8k | 1.7k | 2.3k |
| **System tools** | 10.6k | 10.6k | 10.6k |
| **MCP tools (deferred)** | 24.0k | 25.0k | 21.2k |

### 4.3 분석

- **test-4 (headroom)**가 Messages 토큰이 가장 많은 이유: compress 결과물(압축된 텍스트 + JSON 메타데이터)이 그대로 메시지 히스토리에 남기 때문. 압축 효과가 미래 컨텍스트 절감을 위한 것임에도, 현재 세션에서는 오히려 컨텍스트 증가를 유발함.

- **test-3 (dag-headroom)**가 Messages 토큰이 가장 적은 이유: 각 노드 페이로드가 CCR 해시로 압축 저장되어 컨텍스트에서 제거됨. 분석 과정의 중간 사고 내용이 컨텍스트에 누적되지 않음.

- **test-5 (sequential-thinking)**은 중간값. 8개 사고 단계의 내용이 모두 컨텍스트에 누적되지만, 추가 압축 작업 없어 적절한 수준.

---

## 5. 압축 효율 및 비용 분석

### 5.1 압축 메트릭 비교

| 지표 | test-3 (dag-headroom) | test-4 (headroom) | test-5 (sequential-thinking) |
|------|----------------------|-------------------|------------------------------|
| **압축 대상** | DAG 노드 페이로드 | 보고서 전체 텍스트 | 없음 |
| **원본 토큰** | 530 | 4,408 | - |
| **압축 후 토큰** | 330 | 2,827 | - |
| **절감 토큰** | 200 | 1,581 (메인) / 1,678 (전체) | - |
| **압축률** | **37.74%** | **35.9% (메인)** / 19.1% (전체) | - |
| **절감 비용** | 미측정 | **$0.005** (전체 기준) | - |
| **압축 전략** | CCR(해시 기반) | router:mixed:0.53 | - |
| **복원 가능 여부** | ✅ (ccr_hash로 복원) | ✅ (hash로 복원) | ❌ (미해당) |

### 5.2 압축 접근 방식 차이

```
dag-headroom: 각 노드 완료 시 → 해당 노드 페이로드만 압축
              압축 단위: 노드별 (세밀한 제어)
              → 전체 분석 과정에서 지속적으로 컨텍스트 최적화

headroom:     보고서 완성 후 → 전체 내용을 한 번에 압축
              압축 단위: 문서 전체 (일괄 처리)
              → 향후 대화에서 참조 시 retrieve로 복원

sequential-thinking: 압축 없음
                     모든 사고 내용이 컨텍스트에 그대로 누적
```

### 5.3 실제 비용 임팩트

headroom의 $0.005 절감은 단일 세션 기준으로 소액이지만, 동일 패턴의 반복 작업에서는 의미 있는 절감이 된다. 특히 긴 문서를 반복 참조하는 시나리오에서 retrieve 기반 접근이 유리하다.

---

## 6. 생성 결과물 품질 비교 — 실제 파일 기반

> 3개 파일(django_vs_spring_v3.md, django-spring-comparison-v1.md, django-spring-deep-dive-v1.md)을 직접 정독하여 비교했다.

### 6.1 결과물 규모

| 항목 | test-3 (dag-headroom) | test-4 (headroom) | test-5 (sequential-thinking) |
|------|----------------------|-------------------|------------------------------|
| **생성 파일** | django_vs_spring_v3.md | django-spring-comparison-v1.md | django-spring-deep-dive-v1.md |
| **파일 라인 수** | 637줄 | 617줄 | 877줄 |
| **섹션 수** | **11개** | 7개 | 10개 |
| **비교 표 수** | **24항목 표 1개 + 소표 다수** | 4개 | 5개 |
| **코드 예시 수** | 15+ | 12+ | 15+ |

> **주의**: 줄 수 = 품질이 아니다. test-5의 877줄은 공백·다이어그램 등 비내용 비중이 높다.

### 6.2 항목별 콘텐츠 비교

#### (A) 구조 및 독자 친화성

| 항목 | dag-headroom (v3) | headroom (v1-comparison) | sequential-thinking (v1-deep-dive) |
|------|:-----------------:|:------------------------:|:----------------------------------:|
| **Executive Summary** | ✅ 있음 | ❌ 없음 | ❌ 없음 |
| **역사 정보** | 표 형식 (항목/내용) | 서술형 | 연도별 타임라인 (가장 상세) |
| **구조 방식** | 주제별 나란히 비교 | 프레임워크 단독 분석 → 후반 비교 | 주제별 나란히 비교 |
| **선택 가이드 형식** | 표(상황\|이유) + 플로차트 | 체크리스트 | 플로차트 + 권고 표 |
| **결론 인용구** | 있음 ("빨리 만들고 검증" vs "크게, 오래, 안전하게") | 없음 | 있음 ("빠르게 만들고 싶다" vs "크게 만들고 싶다") |

#### (B) 성능 수치 — 가장 큰 차별점

| 성능 항목 | dag-headroom (v3) | headroom (v1) | sequential-thinking (v1) |
|-----------|:-----------------:|:-------------:|:------------------------:|
| **req/s 벤치마크** | ✅ (Django ~15k, Spring MVC ~35k, WebFlux ~55k) | ❌ 없음 | ❌ 없음 |
| **메모리 수치** | ✅ Django ~50-100MB, Spring ~200-500MB, Native ~30-80MB | ⚠️ ~100MB vs ~300MB~1GB (범위만) | ⚠️ ~50MB vs ~256MB+ (프로세스 기준) |
| **시작 시간** | ✅ Django ~2-5초, Spring ~10-15초, Native ~0.1초 | ⚠️ 정성적 설명 | ⚠️ ~1초 vs ~5~15초 |
| **GraalVM Native 메모리** | ✅ **~30-80MB** (가장 구체적) | ❌ | ❌ |

#### (C) 기술 깊이 — 항목별

| 기술 항목 | dag-headroom (v3) | headroom (v1) | sequential-thinking (v1) |
|-----------|:-----------------:|:-------------:|:------------------------:|
| **비동기: ORM 한계** | ✅ sync_to_async 언급 | ❌ 미언급 | ✅ sync_to_async 코드 예시 |
| **비동기: 백프레셔(backpressure)** | ✅ **언급** | ❌ | ❌ |
| **비동기: R2DBC** | ❌ | ❌ | ✅ 코드 예시 |
| **비동기: Virtual Threads(Java 21)** | ❌ | ❌ | ✅ 명시 |
| **마이크로서비스 기능 비교표** | ✅ **6개 기능 상세 표** (Circuit Breaker, Tracing 포함) | ❌ 1줄 언급 | ⚠️ 다이어그램만 |
| **AOP 코드 예시** | ✅ | ✅ | ✅ |
| **Django Admin 코드** | ⚠️ 간략 언급 | ✅ 상세 코드 | ✅ 상세 코드 |
| **테스팅: 슬라이스 테스트** | ✅ (@WebMvcTest, @DataJpaTest) | ❌ | ✅ (@DataJpaTest, Testcontainers) |
| **ORM: LazyInitializationException 함정** | ✅ **언급** | ❌ | ❌ |
| **개발 파일 수 비교표** | ✅ (Django ~4개 vs Spring ~6-8개) | ❌ | ❌ |
| **Python 3.13 no-GIL** | ✅ **언급** (최신 트렌드) | ❌ | ❌ |
| **AI/ML: LangChain, HuggingFace** | ✅ **명시** | ❌ | ❌ |
| **Spring AI** | ✅ (성장 중) | ❌ | ❌ |
| **OAuth2 코드 예시** | ⚠️ 간략 | ✅ 코드 있음 | ✅ 코드 있음 |
| **보안 기능 ✅/⚠️ 표** | ❌ | ❌ | ✅ (가장 명확한 형식) |
| **생태계 서드파티 패키지 목록** | ⚠️ 표 형식 (간략) | ❌ | ✅ (8개씩 상세 목록) |

#### (D) 요약 비교표 규모

| 비교표 항목 수 | dag-headroom (v3) | headroom (v1) | sequential-thinking (v1) |
|---------------|:-----------------:|:-------------:|:------------------------:|
| 핵심 비교표 항목 | **24개** | 10개 (핵심특성) + 10개(기능별) | 16개 (기술스펙) |
| 별도 표 수 | 소표 다수 + 요약 24개 | 4개 표 | 5개 표 |
| 정량 지표(★ 등) | ★ 5점 척도 | ★ 5점 척도 | ★ 5점 척도 + 우위 컬럼 |

### 6.3 품질 항목별 평가 — 실제 내용 기반

| 측면 | dag-headroom | headroom | sequential-thinking |
|------|:---:|:---:|:---:|
| **논리적 흐름** | ★★★★★ | ★★★★☆ | ★★★★★ |
| **내용 밀도 (줄당 정보량)** | **★★★★★** | ★★★★☆ | ★★★☆☆ |
| **성능 수치 구체성** | **★★★★★** | ★★☆☆☆ | ★★★☆☆ |
| **마이크로서비스 커버리지** | **★★★★★** | ★★☆☆☆ | ★★★☆☆ |
| **비동기 커버리지** | ★★★★☆ | ★★☆☆☆ | **★★★★★** |
| **보안 비교 명확성** | ★★★☆☆ | ★★★☆☆ | **★★★★★** |
| **최신 트렌드 반영** | **★★★★★** (Python 3.13, Spring AI, LangChain) | ★★★☆☆ | ★★★★☆ |
| **선택 가이드 유용성** | **★★★★★** (표+이유+플로차트) | ★★★☆☆ (체크리스트) | ★★★★☆ (플로차트+표) |
| **전체 품질 순위** | **1위** | **3위** | **2위** |

### 6.4 총평

**test-3 (dag-headroom)** 가 가장 정보 밀도가 높은 보고서를 생성했다. 637줄이라는 상대적으로 짧은 분량임에도 불구하고 다른 두 보고서에 없는 내용이 가장 많다: 실제 req/s 벤치마크, GraalVM Native 메모리 수치, 마이크로서비스 6개 기능 비교표, 파일 수 비교표, Python 3.13 no-GIL 언급, LangChain/HuggingFace/Spring AI 생태계 트렌드. DAG의 Critique 노드가 두 프레임워크의 실질적 약점을 날카롭게 짚어내는 데 기여한 것으로 보인다.

**test-5 (sequential-thinking)** 은 877줄로 가장 길지만 정보 밀도는 중간이다. 비동기 섹션(sync_to_async, R2DBC, Virtual Threads)과 보안 비교표(✅/⚠️)는 세 개 중 가장 잘 작성됐다. 단계별 사고 덕분에 각 기능 항목을 빠짐없이 커버했으나, 일부 섹션에서 유사한 내용이 반복된다.

**test-4 (headroom)** 은 코드 예시는 충실하지만 분석 깊이가 상대적으로 얕다. 성능 수치, 마이크로서비스 비교, 최신 트렌드가 빠져 있다. headroom 서버 자체가 압축/복원에 특화된 도구여서 분석 구조를 유도하지 않기 때문이다. 보고서 품질은 순전히 모델의 자유 판단에 의존했다.

---

## 7. MCP 툴 스키마 오버헤드 비교

MCP 툴은 활성화되는 순간 컨텍스트에 스키마 토큰이 적재된다. 이 오버헤드는 매 요청마다 반복 소비된다.

### 7.1 MCP 툴 스키마 토큰 (active 기준)

| MCP 서버 | 툴 이름 | 스키마 토큰 |
|----------|---------|------------|
| **dag-headroom** | `mcp__dag-headroom__dag_headroom` | **385** |
| **headroom** | `mcp__headroom__headroom_compress` | 163 |
|  | `mcp__headroom__headroom_retrieve` | 170 |
|  | `mcp__headroom__headroom_stats` | 68 |
|  | **소계** | **401** |
| **sequential-thinking** | `mcp__sequential-thinking__sequentialthinking` | **903** |

### 7.2 스키마 오버헤드 분석

```
dag-headroom:        385 토큰 (단일 툴, 다목적 action 파라미터)
headroom:            401 토큰 (3개 툴의 합산)
sequential-thinking: 903 토큰 (단일 툴이지만 스키마가 가장 복잡)
```

- **sequential-thinking**의 스키마가 가장 무거운 이유: `thought`, `thoughtNumber`, `totalThoughts`, `nextThoughtNeeded`, `isRevision`, `revisesThought`, `branchFromThought`, `branches` 등 다양한 파라미터 정의 때문
- **dag-headroom**은 단일 툴로 다양한 작업을 처리하면서도 스키마가 가장 경량

---

## 8. 종합 비교표

### 8.1 핵심 지표 요약

| 지표 | test-3 dag-headroom | test-4 headroom | test-5 sequential-thinking |
|------|:-------------------:|:---------------:|:---------------------------:|
| **MCP 툴 스키마 (tokens)** | 385 | 401 | **903** |
| **핵심 툴 호출 횟수** | ~5회 | 2회 | **8회** |
| **총 툴 호출** | ~7회 | ~6회 | **~12회** |
| **Messages 증가 (tokens)** | **22.9k** | 34.5k | 27.1k |
| **최종 컨텍스트 사용률** | **22%** | 28% | 25% |
| **압축률** | 37.74% | 35.9% | - |
| **비용 절감 측정** | 미제공 | **$0.005** | 없음 |
| **생성 파일 라인 수** | 637 | 617 | 877 |
| **내용 밀도 (정보/줄)** | **1위** | 2위 | 3위 |
| **보고서 품질 순위** | **1위** | 3위 | 2위 |
| **구조화 강도** | 강 (DAG) | 없음 | 강 (순차) |
| **병렬 브랜치 지원** | ✅ | ❌ | 제한적 |
| **복원 가능 여부** | ✅ | ✅ | ❌ |

### 8.2 적합 시나리오별 추천

| 시나리오 | 추천 MCP |
|----------|---------|
| 분석 보고서 품질 최우선 | **dag-headroom** |
| 논리적 의존 관계가 있는 복잡한 분석 | **dag-headroom** |
| 긴 문서를 후속 세션에서 재참조 | **headroom** |
| 순서가 명확한 단계별 리서치/작업 | **sequential-thinking** |
| 컨텍스트 최소화가 중요한 경우 | **dag-headroom** |
| 비용 절감을 측정/추적해야 하는 경우 | **headroom** |
| 비동기/보안처럼 기능 항목별 커버리지가 중요한 경우 | **sequential-thinking** |
| 병렬 분석 브랜치가 필요한 경우 | **dag-headroom** |

---

## 9. 결론 및 선택 가이드

### 9.1 각 MCP 서버의 핵심 가치

**dag-headroom — "구조화된 사고 + 컨텍스트 효율 + 최고 품질 결과물"**
- DAG 노드(Objective → Evidence → Critique → Synthesis) 단위의 체계적 분석으로 논리 오류 방지
- **Critique 노드가 두 프레임워크의 실질적 약점을 날카롭게 포착** — req/s 수치, GraalVM Native 메모리, Python 3.13 no-GIL 등 다른 MCP에서 누락된 정보까지 커버
- 중간 사고 내용을 압축 저장해 컨텍스트 효율이 세 가지 중 가장 높음 (22%)
- 결과물 줄 수는 637줄로 가장 짧지만, 정보 밀도는 가장 높음
- 노드 설계와 DAG 구성에 초기 비용 존재
- 복잡한 연구·분석 작업, 병렬 검토가 필요한 비교 분석에 최적

**headroom — "범용 압축 + 비용 추적"**
- 사고 구조를 강제하지 않아 유연하게 사용 가능
- 압축된 콘텐츠를 후속 세션에서 restore해 장기 참조에 강점
- 비용 절감액 측정이 가능해 ROI 추적에 유리
- **분석 품질은 순전히 모델의 자유 판단에 의존** — 구조가 없으므로 깊이 있는 분석을 보장하지 않음
- 현재 세션 컨텍스트는 오히려 가장 많이 증가 (34.5k) — 압축 결과물이 히스토리에 남기 때문
- 대용량 문서 관리, 반복 참조 시나리오, 결과물 보존에 적합

**sequential-thinking — "투명한 단계별 사고 + 기능 커버리지"**
- 가장 직관적이고 자연스러운 단계 분해
- 각 기능 항목을 단계적으로 빠짐없이 다루는 체계적 커버리지 강점
- **비동기 섹션(R2DBC, Virtual Threads), 보안 비교표(✅/⚠️)는 세 개 중 가장 상세**
- 각 사고 단계가 컨텍스트에 모두 보존되어 추적/디버깅 용이
- 압축 없이 컨텍스트가 선형 누적 — 장기 작업 시 컨텍스트 고갈 위험
- 일부 섹션에서 유사 내용이 반복되어 분량 대비 밀도 낮음

### 9.2 의사결정 플로우차트

```
작업 시작
    │
    ├─ 분석 항목 간 논리적 의존 관계가 있는가?
    │       YES → dag-headroom
    │
    ├─ 결과물을 다음 세션에서도 참조/복원해야 하는가?
    │       YES → headroom
    │
    ├─ 단계적으로 진행하되 최대한 상세한 결과가 필요한가?
    │       YES → sequential-thinking
    │
    └─ 컨텍스트 효율이 최우선인가?
            YES → dag-headroom
```

### 9.3 3가지를 조합하는 전략

세 서버는 상호 배타적이지 않다. 실제 고부하 작업에서는 조합이 효과적이다:

1. **탐색 단계**: sequential-thinking으로 분석 구조 수립
2. **실행 단계**: dag-headroom으로 구조화된 실행 + 컨텍스트 최적화
3. **보존 단계**: headroom으로 완성된 결과물 압축 저장 → 후속 세션 활용

---

*본 보고서는 2026-06-07 기준 test-3, test-4, test-5 실행 로그를 직접 분석해 작성했습니다.*
