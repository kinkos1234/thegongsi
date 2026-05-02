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
# DART_API_KEY, JWT_SECRET_KEY, ADMIN_JOBS_TOKEN 등 설정
python -m uvicorn app.main:app --reload --port 8888
```

Swagger: http://localhost:8888/docs

## DB 마이그레이션

로컬 개발은 기본값 `AUTO_CREATE_TABLES=true`라 앱 시작 시 누락 테이블을 자동 생성합니다.
기존 SQLite DB를 쓰고 있다면 새 컬럼은 자동 추가되지 않으므로, 서버 실행 전 한 번 마이그레이션을 적용하세요.
운영은 `AUTO_CREATE_TABLES=false`로 두고 Alembic만으로 스키마를 변경합니다.

```bash
alembic upgrade head
alembic current
```

Fly 배포는 `fly.toml`의 `release_command = "alembic upgrade head"`가 먼저 실행됩니다.

## 테스트

여러 Python이 설치된 로컬에서는 `pytest` 실행 파일과 `python` 인터프리터가 달라질 수 있습니다.
의존성이 설치된 인터프리터를 확실히 쓰도록 아래처럼 실행하세요.

```bash
python -m pytest -q
```

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
