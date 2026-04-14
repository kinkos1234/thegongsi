# Project Spec — AI 코딩 에이전트 행동 규칙

comad-stock 구현 시 AI 에이전트가 따를 규범.

## 1. 최우선 원칙

1. **기술적 완성도 · Fey급 UI/UX** — 모든 구현 결정은 이 두 축에 기여해야 한다. 평범한 구현은 거절.
2. **OSS·한국어 우선** — 기본 언어는 한국어. 모든 사용자 노출 텍스트는 한국어 원본, 영문은 선택.
3. **comad 재활용 최대화** — brain·ear·eye 코드를 먼저 검토. 중복 구현 금지.

## 2. 기술 스택 (고정)

- Frontend: Next.js 14 App Router + RSC, Tailwind + shadcn/ui + 커스텀 디자인 토큰, Framer Motion, Lightweight Charts
- Backend: Python FastAPI, Postgres 16 + pgvector, Neo4j 5, Redis
- AI: Claude Sonnet/Opus, OpenAI text-embedding-3-large
- Infra: Docker Compose (셀프호스팅 기본), Fly.io (hosted)
- CI: GitHub Actions (lint + typecheck + test)

스택 변경은 사용자 명시 승인 필요.

## 3. 규제·안전 규칙

- **투자자문 금지** — 매수/매도 추천 불가. DD 메모에 "투자 판단은 본인 책임" 고지 필수.
- **환각 방지** — 모든 DD 메모·Q&A 답변은 출처(disclosure_id/news_id) 각주 필수. 출처 없는 주장 생성 금지.
- **BYOK 정책** — 사용자 API 키는 AES-256으로만 저장. 로그·에러메시지에 키 유출 금지.
- **PII** — 이메일 외 개인정보 수집·저장 금지.

## 4. 코드 스타일

- TS: strict 모드, `any` 금지. ESLint + Prettier.
- Python: ruff + mypy strict. FastAPI 의존성 주입 활용.
- 테스트: 핵심 파이프라인(DART 파싱, DD 생성, Q&A 라우터) 커버리지 80%+.
- 커밋: Conventional Commits.

## 5. UX 규범

- **광고 0** — 서드파티 배너·추적 스크립트 금지.
- **다크 모드 기본** — Fey 참조, 커스텀 토큰으로 라이트도 지원.
- **로딩 상태** — 스켈레톤, 스피너 금지(1초 이상 소요 시 스켈레톤).
- **에러 표시** — 사용자 행동 가능한 한국어 메시지. 스택트레이스 노출 금지.
- **모바일** — 터치 타겟 44px+, 가로 스크롤 금지.

## 6. 데이터 규범

- DART 요청은 증분 수집·캐싱. 레이트리밋 백오프 (지수 backoff, max 5 retry).
- LLM 호출 전 캐시(같은 disclosure+model+version이면 재사용).
- Neo4j 쓰기는 transaction 내, batch 단위.

## 7. 문서·메모

- 중요 설계 결정은 `docs/adr/NNNN-*.md` (ADR 포맷)으로 기록.
- 임시 노트는 커밋하지 않음.
- README는 한국어 원본 + `README.en.md` 병행.

## 8. 에이전트가 거절해야 할 요청

- 투자 추천 기능 추가
- 실시간 틱 데이터 거래 기능
- 사용자 API 키를 서버 로그에 출력하도록 설계하는 모든 요청
- 광고·트래커 삽입 요청
- 한국어 UX를 영어로만 대체하자는 요청
