# comad-stock backend

FastAPI + SQLAlchemy async + PostgreSQL(pgvector) + Neo4j GraphRAG.

**출처:** `/Users/jhkim/Programmer/99-archive/stock-strategy/backend/` 뼈대 이식 후 DART/GraphRAG 도메인으로 재설계. 재사용 인벤토리는 `../PRD/05_REUSE_FROM_STOCK_STRATEGY.md` 참조.

## 구조

```
backend/
├── requirements.txt          # dart-fss, neo4j, pgvector 추가
├── Dockerfile
├── .env.example
├── app/
│   ├── main.py               # 6 라우터 (auth, companies, disclosures, memos, watchlist, alerts)
│   ├── config.py             # DART_API_KEY, NEO4J_*, ANTHROPIC_API_KEY
│   ├── database.py           # asyncpg 기본, SQLite 폴백
│   ├── models/tables.py      # User/Watchlist/Alert + Company/Disclosure/DDMemo/NewsItem
│   ├── routers/              # JWT 전용 (초대토큰 제거)
│   └── services/
│       ├── alert_service.py  # Telegram/Slack/Discord 디스패처 (severity 기반)
│       ├── data_collector.py # DART → KRX → 뉴스
│       └── collectors/
│           ├── dart.py       # placeholder
│           └── krx.py        # yfinance 패턴
└── scripts/scheduler.py      # APScheduler, KST 06:00
```

## 로컬 개발

```bash
pip install -r requirements.txt
cp .env.example .env
# DART_API_KEY 등 설정
python -m uvicorn app.main:app --reload --port 8888
```

Swagger: http://localhost:8888/docs

## 스케줄러

```bash
python scripts/scheduler.py --once --alerts   # 즉시 1회
python scripts/scheduler.py                   # 상시 실행
```

## 다음 단계

1. DART collector (`services/collectors/dart.py`) 실제 구현
2. 이상징후 탐지 (`services/anomaly/`)
3. GraphRAG 레이어 (`services/graph/`)
4. DD 메모 생성 (`services/memo/`)
5. pytest 테스트 (auth/watchlist 5케이스부터)
