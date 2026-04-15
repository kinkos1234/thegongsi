# The Gongsi · 더공시

**Korean disclosures, deciphered.**
*DART-native AI research terminal for Korean equities — open source, Korean-first.*

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange)](#)
[![Stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20Next.js%2016%20%2B%20Neo4j-blue)](#)

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

## 3개 차별점

- **DART 공시 AI 분석** — 자동 한국어 요약 + 이상징후 severity(low/med/high) 플래그.
- **GraphRAG 자연어 Q&A** — 공급망·경쟁사·인물 그래프 위 자연어 질의. Cypher 자동 생성.
- **AI DD 메모** — 종목 → bull/bear/thesis 한국어 메모(공시+뉴스+실적 통합, 버전 히스토리).

## 스택

- **Backend:** FastAPI 0.115 · SQLAlchemy 2.0 async · PostgreSQL(pgvector) · Neo4j 5 · dart-fss · Anthropic Claude
- **Frontend:** Next.js 16 App Router · React 19 · Tailwind 4 · Recharts 3
- **Infra:** Docker Compose · APScheduler (KST 06:00 일일 배치)

## 빠른 시작

```bash
# 의존성 실행
docker compose up -d postgres neo4j

# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # DART_API_KEY, ANTHROPIC_API_KEY, NEO4J_* 설정
python scripts/init_graph.py        # Neo4j 스키마
python scripts/seed_graph.py        # (선택) HBM 공급망 시드
python -m uvicorn app.main:app --reload --port 8888

# Frontend
cd ../frontend
npm install && npm run dev   # http://localhost:3333

# 데이터 수집 1회
cd ../backend
python scripts/scheduler.py --once --alerts
```

## 프로젝트 구조

```
thegongsi/
├── PRD/                    # PRD · 데이터모델 · Phase · 재사용맵 · 리뷰
├── docs/
│   ├── DESIGN.md           # Fey급 UI 시스템
│   ├── GRAPH_PIPELINE.md   # 5만 엣지 로드맵
│   ├── DEMO_ASSETS.md      # 스크린샷 캡처 가이드
│   └── launch/             # Show HN + dev.to 포스팅 초안
├── bench/                  # 20개 gold-query + recall/precision 러너
├── backend/                # FastAPI + 수집기 + GraphRAG + DD 메모
└── frontend/               # Next.js 16 + Tailwind 4 + Recharts
```

## 로드맵

- **Phase 1 (α 현재):** DART 수집·이상 공시, DD 메모 AI, Ask (multi-tool retriever), KOSPI/KOSDAQ 대시보드, BYOK
- **Phase 2:** 매직링크 인증, DART 본문 HTML entity extraction (5만 엣지 목표), 실적 콜 transcript, Managed hosted
- **Phase 3:** 기관 API, 포트폴리오 리밸런싱, 소형주 IPO 리서치, Redis/HA 스케일

## 런칭 체크리스트

[LAUNCH.md](LAUNCH.md) — Day-0 배포 checklist · Show HN 체크리스트 · 30일 성공 지표.

## 기여

[CONTRIBUTING.md](CONTRIBUTING.md) 참고. 이슈·디스커션 환영.

## 라이선스

MIT. AI 생성 메모는 투자자문이 아닌 참고 자료입니다.
