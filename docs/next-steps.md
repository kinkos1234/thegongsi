# Next Steps

## 확정됨

- 포지션: DART-native AI 주식 리서치 터미널, OSS, 한국어 우선 ([positioning.md](positioning.md))
- 이름: `comad-stock` (확정)
- MVP 스코프: KOSPI 200 우선, 이후 코스닥·해외 확장
- 구조: comad-world 독립 자매 레포
- 두 북극성: 기술적 완성도 + Fey급 UI/UX

## 즉시 해야 할 것

1. **PRD 4종 생성** — `/show-me-the-prd`로 인터뷰 기반 (PRD, 데이터 모델, Phase 분리, 프로젝트 스펙).
2. **기술 스택 결정** — 아래 초안 검토·확정.
3. **DESIGN.md 작성** — Fey급 UI/UX를 위해 디자인 시스템 먼저 (색·타이포·모션·정보밀도 규칙).
4. **독립 Git 레포 초기화** — `comad-stock` (MIT).

## 기술 스택 (초안)

**Frontend (Fey급 UX 핵심):**
- Next.js 14 App Router + React Server Components
- Tailwind CSS + shadcn/ui (커스텀 디자인 토큰)
- Framer Motion (절제된 마이크로 인터랙션)
- TanStack Query + Zustand
- 차트: ECharts 또는 Lightweight Charts (TradingView 오픈소스)

**Backend:**
- Python FastAPI (comad-eye와 동일 스택으로 일관)
- Postgres + pgvector (문서 임베딩)
- Neo4j (comad-brain 재활용, 엔티티 그래프)
- Redis (캐시·잡 큐)

**Data:**
- **DART OpenAPI** (무료, 하루 10,000건 한도) — 핵심 소스
- **KRX 시세** — KRX 정보데이터시스템 또는 pykrx
- **해외 주식** — Alpha Vantage 무료 티어 시작, 확장 시 Polygon
- **뉴스** — comad-ear 재활용 (한경·매경·연합뉴스 RSS)

**AI:**
- Claude Sonnet (DD 메모·요약), Opus (이상징후 분석)
- 임베딩: OpenAI text-embedding-3-large 또는 KoSimCSE

**인프라:**
- Docker Compose (셀프호스팅 기본)
- GitHub Actions CI
- hosted: Fly.io 또는 Railway (월 $20 이내)

## 리스크

1. **DART API 레이트 리밋** — 10,000건/일. 캐싱·증분 수집 필수.
2. **KRX 실시간 시세 라이선싱** — 실시간은 유료. MVP는 15분 지연.
3. **LLM 비용** — DD 메모 1건당 ~$0.10 예상. BYO API 키 정책.
4. **규제** — 투자자문업 아님을 명시 (정보 제공·AI 요약). 매수·매도 추천 금지 프롬프트 규칙.
5. **Fey급 UX 완성도** — 솔로 리스크 최대 포인트. 디자인 시스템 초기 투자 필수.

## 오픈 질문

- 첫 공개 시기 목표 (Show HN / GeekNews)?
- hosted 버전 론칭 시점?
