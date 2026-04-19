# The Gongsi · 더공시

**Korean disclosures, deciphered.**
*DART-native AI research terminal for Korean equities — open source, Korean-first.*

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v0.3.1-blue)](https://github.com/kinkos1234/thegongsi/releases/tag/v0.3.1)
[![Stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20Next.js%2016%20%2B%20Neo4j-blue)](#)
[![Live](https://img.shields.io/badge/live-thegongsi.vercel.app-brightgreen)](https://thegongsi.vercel.app)

> **TL;DR (English)**
> Korean listed companies file ~1M disclosures per year on DART (the national electronic filing system, like SEC EDGAR). **95% is routine noise; 5% flips investment theses** — going-concern doubt, insider trades, equity dilution, major-shareholder changes. **The Gongsi** auto-summarizes every filing in Korean, rule-flags anomalies, and answers natural-language supply-chain questions via GraphRAG (Cypher over Neo4j + Claude multi-tool). Self-hostable with BYOK. For DIY investors and EM-Asia desks at global funds.

한국 리테일 투자자에게는 Fey·Seeking Alpha 수준의 진지한 리서치 도구가 없다. 네이버 증권은 광고+뉴스, 토스증권 인사이트는 단편적, 증권플러스는 가격 중심. **The Gongsi가 그 공백을 채운다.**

## 우리가 믿는 것

- **공시의 95%는 노이즈, 5%가 인생을 바꾼다.** 문제는 그 5%를 걸러낼 시간이 없다는 것.
- 한국 기업 관계는 지분·공급망·인사로 얽힌 **그래프**다. SQL도 벡터 검색도 이걸 혼자 풀 수 없다.
- **AI는 조언자가 아니라 독해기**다. 우리는 bull/bear 논리를 제공하지 목표가·매수추천을 제공하지 않는다.

## 북극성

1. **기술적 완성도** — GraphRAG 기반 DART 공시 분석, 기업 엔티티 그래프, AI DD 메모.
2. **Fey급 UI/UX** — 광고 0, 정보 밀도와 심미성 양립. 네이버 증권 두 세대 도약.

## 5개 차별점

- **DART 공시 AI 분석** — 자동 한국어 요약 + 이상징후 severity(low/med/high) 플래그.
- **GraphRAG 자연어 Q&A** — 공급망·경쟁사·인물 그래프 위 자연어 질의. Cypher 자동 생성.
- **AI DD 메모** — 종목 → bull/bear/thesis 한국어 메모(공시+뉴스+실적 통합, 버전 히스토리).
- **공급망 그래프** — 41개 산업 범주 187 SUPPLIES 엣지. LLM extractor 가 매주 DART 공시 본문에서 신규 관계 자동 추출.
- **지배구조 렌즈** *(v0.3.1)* — DART document.xml 본문을 LLM 이 읽어 최대주주·임원·법인 지분 자동 추출(Phase 2). 모기업·자회사 덴드로그램, 순환출자 DFS 감지, 관계 그래프(자체 force-directed physics, d3 없음). canonical name dedup + KOSPI 우선 fuzzy ticker 매칭으로 variant 이름도 통합.

## 실데이터 (v0.3.1 / 2026-04-19)

```
disclosures:       2,767 rows (since 2025-04-21, 일평균 7.6)
earnings events:   Q1 2026 21건 (매출/영업익/순익 단위 정규화: 백만원 기준)
calendar events:   27 upcoming (권리락·배당락·납입일·상장일, dedup 적용)
supply chain:      187 SUPPLIES edges / 41 categories / 256 company 노드
companies:         3,959 (KOSPI 836 + KOSDAQ 1,778 + 기타)
governance:        major_shareholders · insiders · corporate_ownership 3 tables
                   + HOLDS_SHARES (Company→Company) edges on Neo4j
                   + 순환출자 DFS detection (max depth 5)
                   + Phase 2 본문 기반 LLM 추출 (9/10 watchlist 커버)
```

## 스택

- **Backend:** FastAPI 0.115 · SQLAlchemy 2.0 async · PostgreSQL(Supabase) · Neo4j 5(AuraDB) · OpenDART REST · Anthropic Claude (BYOK 3-tier)
- **Frontend:** Next.js 16 App Router · React 19 · Tailwind 4 · Recharts 3 · `loading.tsx` 스켈레톤 (`/c/[ticker]`·`/watchlist`·`/settings`)
- **Infra:** Vercel Hobby · Fly.io Free (nrt) · GitHub Actions cron (매일 KST 06:00 DART 수집 + KST 08:00 잠정실적 + 매 10분 keepalive). 월 $0.
- **알림:** Discord Embed(admin 글로벌 webhook, severity 이모지·종목명·DART 링크 포함) + user-level BYOK(telegram/slack/discord).

## 빠른 시작

```bash
# 의존성 실행
docker compose up -d postgres neo4j

# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # DART_API_KEY, ANTHROPIC_API_KEY, NEO4J_* 설정

# ✨ 1회 부트스트랩 — 시장 최근 90일 공시 + 이상 공시 + 그래프 시드
python scripts/bootstrap.py --seed              # 8~10분 소요, ~2,000 disclosures
python scripts/seed_supply_chains.py            # 공급망 seed (41 cat / 171 edges)

# 서버 기동
python -m uvicorn app.main:app --reload --port 8888

# Frontend
cd ../frontend
npm install && npm run dev   # http://localhost:3333

# 데이터 수집 1회 (로컬 개발용)
cd ../backend
python scripts/scheduler.py --once --alerts
```

### 프로덕션 배포 (Fly + Vercel, 월 $0)

```bash
# Backend: Fly.io (admin cron 구조)
cd backend && fly launch --no-deploy
fly secrets set DART_API_KEY=... ANTHROPIC_API_KEY=... \
    NEO4J_URL=... NEO4J_USER=... NEO4J_PASSWORD=... \
    DATABASE_URL=... JWT_SECRET_KEY=... FIELD_ENCRYPTION_KEY=... \
    ADMIN_JOBS_TOKEN=<랜덤> DISCORD_WEBHOOK_URL=<옵션>
fly deploy

# Frontend: Vercel (GitHub 연동 자동 배포)
# NEXT_PUBLIC_API_URL=https://<fly-app>.fly.dev 만 Vercel 대시보드에 설정

# GitHub Actions: cron.yml · keepalive.yml 자동 활성
# Secrets: FLY_API_BASE, ADMIN_JOBS_TOKEN
```

## 프로젝트 구조

```
thegongsi/
├── .github/workflows/
│   ├── ci.yml              # 타입체크 + pytest (Python 3.12 + Node 20)
│   ├── cron.yml            # 매일/매주 DART 수집 · 실적 · 권리락 · DB 백업
│   └── keepalive.yml       # Fly + AuraDB idle-hibernate 방지 (10분/6h)
├── docs/
│   ├── DESIGN.md           # Fey급 UI 시스템
│   ├── GRAPH_PIPELINE.md   # 5만 엣지 로드맵
│   └── launch/             # Brunch · Velog · Show HN · Threads 초안
├── bench/                  # 20개 gold-query + recall/precision 러너
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   │   ├── admin_jobs.py      # cron 트리거 + graph_ping + 공급망 추출
│   │   │   ├── earnings.py        # Q1 실적 (company JOIN for 종목명)
│   │   │   ├── calendar.py        # 권리락·배당락·납입일·상장일
│   │   │   ├── alerts.py          # BYOK 알림 (telegram/slack/discord)
│   │   │   └── …
│   │   └── services/
│   │       ├── graph/
│   │       │   ├── supply_chain_extractor.py  # DART 본문 → 4종 관계 LLM 추출
│   │       │   └── qa.py                       # GraphRAG multi-tool
│   │       ├── collectors/
│   │       │   └── earnings.py    # 단위 정규화 (백만원)
│   │       └── alert_service.py   # Discord Embed (종목명 · DART 링크 · 이모지)
│   ├── data/supply_chains.yaml    # 41 cat / 171 관계 seed
│   └── scripts/                   # scan_*, seed_*, bootstrap
└── frontend/
    ├── app/
    │   ├── c/[ticker]/loading.tsx # 스켈레톤 (2.2s SSR 중 표시)
    │   └── …
    └── components/RecentEarnings.tsx  # 랜딩 최근 실적 Top 5
```

## 로드맵

- **v0.1 (2026-04-15):** α 론칭 — DART 수집·이상 공시·DD 메모·Ask·BYOK.
- **v0.2 (2026-04-18):** cron 실배선 · admin_jobs 동기 응답 · 공급망 그래프 (187 edges / 41 categories · seed+LLM extractor) · 단위 정규화 earnings · loading.tsx · keepalive · Discord Embed alerts.
- **v0.3 (2026-04-19):** DART 지배구조 entity extraction (최대주주·임원·법인 지분) · 순환출자 DFS 감지 · OwnershipDendrogram (가로 가지 그래프) · RelatedCompanies 자체 force-directed physics · PulseRibbon 시장 맥박 · CoverageStats 트러스트 시그널 · EditorialMasthead · ConventionOnboarding (KR/US) · 무료 Hahmlet + EB Garamond 폰트 · LoginGate · Next.js 16 dynamic icon.
- **v0.3.1 (2026-04-19 현재):** governance Phase 2 (document.xml 본문 fetch → LLM 추출) · canonical name dedup + KOSPI 우선 fuzzy ticker 매칭 · watchlist 자동 governance 파이프라인 · historical_backfill admin job (days 스케일 max_rows 2000~15000) · daily cron 윈도우 1→3일 sliding · calendar (ticker, event_type, event_date) dedup (기재정정 중복 제거) · PulseRibbon sparse UX (오늘 점선 marker, "활동 X/N일" meta) · CI Node.js 24 호환 업그레이드.
- **v0.4+:** 실적 콜 transcript, Managed hosted, 기관 API.

## 런칭 체크리스트

[LAUNCH.md](LAUNCH.md) — Day-0 배포 checklist · Show HN 체크리스트 · 30일 성공 지표.
[CHANGELOG.md](CHANGELOG.md) — 변경 이력.

## 기여

[CONTRIBUTING.md](CONTRIBUTING.md) 참고. 이슈·디스커션 환영.

## 관련 글

- 기술 장문 (Velog): *pgvector를 버리고 Claude tool_use 로 — 한국 DART 공시를 해석하는 AI 리서치 터미널*
- 투자자용 장문 (Brunch, 발행 대기): *DART를 수년간 뒤진 개인투자자가 결국 자기 도구를 만들었다* (`docs/launch/brunch-investor.md`)

## 라이선스

MIT. AI 생성 메모는 투자자문이 아닌 참고 자료입니다.
