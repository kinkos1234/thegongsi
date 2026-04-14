# Phases

기한 없음, 품질 우선. 체크리스트로 진행 상황 추적.

## Phase 1 — MVP (KOSPI 200, OSS 첫 공개)

### 기반
- [ ] Next.js 14 App Router + FastAPI + Postgres(pgvector) + Neo4j + Redis 세팅
- [ ] Docker Compose 셀프호스팅 패키지 (`docker compose up`으로 구동)
- [ ] 디자인 시스템 (토큰·색·타이포·모션) — Fey급 UX 기준선
- [ ] 이메일+비밀번호 인증 + BYOK(Anthropic/OpenAI 키 AES-256 저장)
- [ ] CI (GitHub Actions, lint/typecheck/test)

### 데이터 수집
- [ ] DART OpenAPI 클라이언트 (KOSPI 200 기업 공시 증분 수집, 레이트리밋·재시도)
- [ ] KRX 시세 (15분 지연, pykrx 기반 일일 갱신)
- [ ] 뉴스 RSS 수집 (comad-ear 재활용, 한경·매경·연합)
- [ ] 기업 레지스트리 시드 (KOSPI 200 corp_code·ticker 매핑)

### AI 파이프라인
- [ ] DART 공시 AI 요약 + 이상징후 감지 (severity 3단계)
- [ ] 엔티티 추출·관계 저장 (Neo4j, comad-brain 재활용)
- [ ] AI DD 메모 생성 (bull/bear, 버전 관리, 출처 각주 필수)
- [ ] GraphRAG Q&A (Cypher 자동 생성 + pgvector 하이브리드 검색)

### UI
- [ ] 종목 대시보드 (시세+차트+공시 타임라인+뉴스)
- [ ] DD 메모 뷰어 (버전 히스토리·출처 각주·재생성 버튼)
- [ ] Q&A 챗 UI (인용·Cypher 디버그 패널)
- [ ] 워치리스트 + 공시 피드
- [ ] 모바일 반응형 레이아웃

### 론칭 준비
- [ ] README 한국어/영문
- [ ] 데모 사이트 1개 (Fly.io)
- [ ] dev.to 한국어 글 초안
- [ ] GeekNews·Show HN 드래프트

## Phase 2 — 확장 (KOSDAQ, 포트폴리오, 알림)

- [ ] KOSDAQ 주요 종목 확장 (시총 상위 200)
- [ ] 실적 콜 오디오 수집 + Whisper 전사 + AI 요약
- [ ] 포트폴리오 트래킹 (수동 입력, Plaid 없이)
- [ ] 공시·이상징후 알림 (웹훅·이메일·텔레그램 봇)
- [ ] 주간 DD 브리핑 (워치리스트 일괄 재생성, 크론)
- [ ] 영문 DD 메모 옵션 (자동 번역)
- [ ] 매직링크 로그인 (메일 서버 구축)

## Phase 3 — 고도화 (글로벌·매니지드·스위트)

- [ ] 해외 종목 지원 (Alpha Vantage → Polygon 전환)
- [ ] Managed hosted SaaS (월 9,900원 티어)
- [ ] 기관용 API (리서치 보조·컴플라이언스)
- [ ] 백테스트·팩터 스크리너
- [ ] 엔티티 그래프 시각화 (공급망 맵, 인사이더 관계도)
- [ ] 소셜 레이어 (공개 DD 메모 공유·코멘트)
