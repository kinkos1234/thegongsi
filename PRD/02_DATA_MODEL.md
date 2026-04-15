# Data Model

> **Phase 1 scaffold 현황 (2026-04-15):** `backend/app/models/tables.py`는 이 문서의 **간소화 서브셋**이다.
> - 구현됨: User, WatchListItem, AlertConfig, AlertHistory, Company, Disclosure, DDMemo, DDMemoVersion, NewsItem
> - **미구현 (Phase 1 중 추가):** AnomalySignal은 Disclosure에 인라인 컬럼(`anomaly_severity`, `anomaly_reason`)으로 시작, 규모 커지면 분리. QASession/QATurn, EarningsEvent, Embedding(pgvector), BYOK 필드(User.byok_*), Person/Product(Neo4j)는 Phase 1 후반에 추가.
> - ID: UUID 문자열 12자 prefix(`uuid4().hex[:12]`) 사용 — 아래 스펙의 `uuid PK`와 등가.
> - Portfolio/PortfolioHolding는 stock-strategy에서 이식 예정 (Phase 2).

## 관계도

```
User 1---N Watchlist N---M Company
Company 1---N Disclosure 1---1 AnomalySignal?
Company 1---N DDMemo (버전 관리, AI 생성)
Company 1---N NewsArticle
Company 1---N EarningsEvent
Company N---M Company (경쟁·공급망, Neo4j)
Company N---M Person (CEO·대주주·등기이사, Neo4j)
User 1---N QASession 1---N QATurn
Disclosure 1---N Embedding (pgvector)
```

## Postgres 스키마

### User
| 필드 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| email | text unique | |
| password_hash | text | bcrypt |
| byok_anthropic_key | text | AES-256 암호화 |
| byok_openai_key | text | AES-256 암호화 |
| created_at | timestamptz | |

### Company
| 필드 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| ticker | varchar(6) unique | 005930 등 |
| name_ko | text | 삼성전자 |
| name_en | text | Samsung Electronics |
| sector | text | |
| market | enum | KOSPI, KOSDAQ |
| corp_code | varchar(8) | DART 고유 코드 |
| market_cap | bigint | 일일 갱신 |

### Watchlist
| 필드 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK | |
| company_id | uuid FK | |
| note | text | 사용자 메모 |
| added_at | timestamptz | |

### Disclosure
| 필드 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| company_id | uuid FK | |
| dart_id | varchar(14) unique | DART 접수번호 |
| type | text | 사업보고서·주요사항 등 |
| title | text | |
| filed_at | timestamptz | |
| raw_url | text | DART 원문 링크 |
| summary_ai | text | 한국어 요약 |
| summary_model | text | claude-sonnet-4-6 등 |
| generated_at | timestamptz | |

### AnomalySignal
| 필드 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| disclosure_id | uuid FK | |
| severity | enum | low, medium, high |
| reason | text | 한국어 설명 |
| detected_at | timestamptz | |

### DDMemo
| 필드 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| company_id | uuid FK | |
| version | int | 1부터 증가 |
| bull_md | text | Markdown bull 논리 |
| bear_md | text | Markdown bear 논리 |
| sources_json | jsonb | 출처 목록 (disclosure_id, news_id, ...) |
| model | text | |
| triggered_by | uuid FK user.id | |
| generated_at | timestamptz | |

### NewsArticle
| 필드 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| company_id | uuid FK | |
| source | text | 한경·매경·연합 등 |
| url | text | |
| title | text | |
| published_at | timestamptz | |
| sentiment | numeric(3,2) | -1.0 ~ 1.0 |

### EarningsEvent (Phase 2)
| 필드 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| company_id | uuid FK | |
| quarter | varchar(8) | 2026Q1 |
| scheduled_at | timestamptz | |
| transcript_url | text | |
| summary_ai | text | |

### QASession
| 필드 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK | |
| title | text | |
| created_at | timestamptz | |

### QATurn
| 필드 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| session_id | uuid FK | |
| question | text | |
| answer_md | text | |
| cypher_used | text | Neo4j 질의 로그 |
| citations_json | jsonb | 인용 출처 |
| created_at | timestamptz | |

### Embedding (pgvector)
| 필드 | 타입 | 비고 |
|---|---|---|
| id | uuid PK | |
| source_type | enum | disclosure, news, transcript |
| source_id | uuid | polymorphic FK |
| chunk_idx | int | |
| chunk_text | text | |
| vector | vector(3072) | text-embedding-3-large |

## Neo4j 그래프

### 노드
- `(:Company {corp_code, ticker, name_ko})`
- `(:Person {id, name_ko, role})`
- `(:Product {id, name, category})`

### 관계
- `(Company)-[:COMPETES_WITH {strength}]->(Company)`
- `(Company)-[:SUPPLIES {category, since}]->(Company)`
- `(Company)-[:OWNS {pct}]->(Company)` — 지분 구조
- `(Person)-[:LEADS {role, since}]->(Company)`
- `(Person)-[:HOLDS {pct}]->(Company)` — 대주주·인사이더

## 인덱스

- Postgres: `disclosure(company_id, filed_at DESC)`, `news(company_id, published_at DESC)`, `embedding USING hnsw (vector vector_cosine_ops)`
- Neo4j: `Company.corp_code` unique, `Person.id` unique
