# 05. stock-strategy 재사용 인벤토리

**원본:** `/Users/jhkim/Programmer/99-archive/stock-strategy/` (구 MarketPulse — FastAPI + Next.js 16, 18 pytest, 동작 검증 완료)
**결정:** 폐기 ❌ → 뼈대 이식 ✅. Phase 1 BE 예상 2~3주 단축.

## 1. 그대로 이식 (As-is, 리네임만)

| 원본 경로 | 대상 경로 | 비고 |
|---|---|---|
| `backend/requirements.txt` | `backend/requirements.txt` | + `dart-fss`, `neo4j`, `pgvector`, `asyncpg` 추가 |
| `backend/Dockerfile` | `backend/Dockerfile` | 그대로 |
| `backend/app/database.py` | `backend/app/database.py` | SQLite → PostgreSQL(asyncpg) 전환만 |
| `backend/app/__init__.py` | `backend/app/__init__.py` | 비어있음 |
| `backend/scripts/scheduler.py` | `backend/scripts/scheduler.py` | 잡 함수 내용만 교체 (뼈대는 동일) |
| `docker-compose.yml` | `docker-compose.yml` | + neo4j, postgres 서비스 |

## 2. 적응 이식 (패턴 유지, 도메인 교체)

| 원본 | 대상 | 수정 포인트 |
|---|---|---|
| `app/main.py` | `app/main.py` | router 목록 교체 (dart, disclosure, company, graph, memo) |
| `app/config.py` | `app/config.py` | `alpha_vantage/fred` 키 → `dart_api_key`, `neo4j_url`, `anthropic_api_key`(BYOK 대비) |
| `app/routers/__init__.py` | `app/routers/__init__.py` | `verify_token`(초대토큰) **삭제**, JWT 의존성만 유지 |
| `app/routers/auth.py` | `app/routers/auth.py` | bcrypt+JWT 그대로. Phase 2 매직링크 전환 예정 |
| `app/routers/watchlist.py` | `app/routers/watchlist.py` | ticker 컬럼 그대로 (KRX 6자리 코드) |
| `app/routers/portfolio.py` | `app/routers/portfolio.py` | Phase 2에서 이식 (리밸런싱 AI 프롬프트만 DD 메모 스타일로) |
| `app/routers/alerts.py` | `app/routers/alerts.py` | 임계치: F&G/VIX → 공시 이상징후 severity |
| `app/services/alert_service.py` | `app/services/alert_service.py` | Telegram/Slack/Discord 디스패처 그대로. 트리거 로직만 교체 |
| `app/services/collectors/korean_market.py` | `app/services/collectors/krx.py` | yfinance 패턴 유지, KOSPI 200으로 확장 |
| `app/services/data_collector.py` | `app/services/data_collector.py` | 순서: dart → krx → news |
| `backend/tests/` | `backend/tests/` | auth/watchlist 5케이스 그대로, 나머지는 재작성 |

## 3. 모델 재설계 (부분 재사용)

**유지:** `User`, `WatchListItem`, `UserPreference`, `AlertConfig`, `AlertHistory`, `Portfolio`, `PortfolioHolding`
**버림:** `MarketSentiment`, `EconomicIndicator`, `Report`, `ReportSection`, `Backtest`, `AccessToken`
**신규 필요:** `Company`, `Disclosure`, `DDMemo`, `DDMemoVersion`, `GraphQuery`, `NewsItem`, `Filing`(DART 원문 캐시)

`02_DATA_MODEL.md`와 교차 검증 후 확정.

## 4. 완전 폐기

- `app/services/collectors/alpha_vantage.py`, `fear_greed.py`, `fred.py` — 글로벌 매크로
- `app/services/ai_report.py`, `auto_report.py`, `market_analyzer.py` — 일일 리포트 파이프라인 (DD 메모와 철학 다름, 신규 작성)
- `app/services/backtest_service.py` — Phase 2까지 보류 (AI 시그널 검증 로직은 추후 재활용 가능)
- `app/routers/sentiment.py`, `economic.py`, `reports.py`, `preferences.py`(초안) — 도메인 불일치
- 초대 토큰 인증 (`AccessToken` 모델, `verify_token`, `?token=` 쿼리) — 이메일/JWT만

## 5. Frontend 재사용 (별도 평가 필요)

`frontend/src/`의 `Navigation`, `AuthGate`, `ErrorBoundary`, `LoadingSkeleton`, `api.ts` 클라이언트는 이식 후보.
단, **Fey급 UI 목표** 때문에 디자인 시스템 먼저 세운 뒤 컴포넌트는 신규 작성 권장. Recharts 3 채택만 확정.

## 6. 이식 순서

1. `backend/` 뼈대 이식 (이 문서 §1~§2) — **현재 진행**
2. 모델 재설계 (§3) → `02_DATA_MODEL.md` 업데이트
3. DART collector 구현 (dart-fss 기반)
4. GraphRAG 레이어 추가 (`services/graph/` 신규)
5. DD 메모 파이프라인 (`services/memo/` 신규)
6. Frontend Fey급 디자인 시스템 설계 → 컴포넌트 작성
