# dag-thinking 개발 가이드

## TDD 워크플로우 (반드시 준수)

**RED → GREEN → REFACTOR 순서를 절대 어기지 말 것.**

1. 스펙 정의 (PLAN.md 기준)
2. **RED**: 구현 코드 없이 실패하는 테스트 먼저 작성
3. **GREEN**: 테스트를 통과시키는 최소 구현 작성
4. 전체 테스트 스위트 실행: `.venv/Scripts/python.exe -m pytest tests/ -q`
5. **REFACTOR**: 동작 유지하며 코드 정리
6. ruff: `uv run ruff check src/ --fix && uv run ruff format src/`
7. git commit

구현 코드를 테스트 없이 먼저 작성하는 것은 TDD 원칙 위반이다.

## 소스 파일 편집 원칙

- 항상 `src/` 디렉토리의 원본 파일을 편집할 것 (배포본 편집 금지)
- 편집 후 반드시 `uv run ruff format src/` 실행
- 소스 파일 목록: `src/server.py` (FastMCP 레이어), `src/actions.py` (비즈니스 로직), `src/db.py` (DB 프리미티브), `src/compressor.py` (CCR 압축기)

## PLAN.md = 스펙 문서

PLAN.md가 스펙 역할을 겸한다 (별도 SPEC.md 없음).
기능 추가/변경 시 PLAN.md에 먼저 명세한 뒤 테스트를 작성한다.

## Windows 인코딩 주의사항

- Python 소스 파일: UTF-8 BOM-less 유지
- YAML, 설정 파일: ASCII 범주 문자만 사용 (cp949, BOM, Unicode 화살표 금지)
- 커밋 메시지: 한국어 가능, 단 cp949 특수문자 주의

## 의존성 원칙 (Lightweight)

`fastmcp>=3.3.1`, `pydantic>=2.13.4`, 표준 라이브러리만 허용.
ML 라이브러리(torch, transformers 등) 사용 금지.
