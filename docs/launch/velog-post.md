# pgvector를 버리고 Claude tool_use로: 한국 DART 공시를 해석하는 AI 리서치 터미널을 만들었다

> **태그**: `#graphrag` `#fastapi` `#nextjs` `#claude` `#neo4j` `#오픈소스` `#한국주식`
> **요약**: DART 공시 966건에서 루틴을 걸러내고 "진짜 신호"만 꺼내는 리서치 터미널을 2주 만에 개발 완료했다. GraphRAG 경로에서 pgvector+SBERT를 버리고 Claude tool_use 기반 multi-tool agent로 대체했는데, 벤치 recall 0.75 → 1.0으로 올랐다.

---

## 왜 또 하나의 주식 툴인가

네이버 증권을 매일 봐도 나는 삼성전자 공시 중 뭐가 "진짜 이상한지" 모른다. 연 100만 건 올라오는 DART 공시 중 99%는 정기보고·배당결정 같은 루틴이고, 1%가 상장폐지·감사거절·최대주주 변경처럼 투자자를 직격한다. 문제는 **그 1%를 골라낼 도구가 없다**는 것이다.

- **Fey / Seeking Alpha**는 아름답지만 영어 전용, 한국 공시 미커버
- **네이버 증권**은 정보는 다 있지만 편집 관점이 없고 광고 도배
- **Hindenburg Research** 톤의 탐사 리서치를 평범한 개인이 쓸 수 있는 UI로

그래서 만들었다. **The Gongsi** — MIT 라이선스, self-hostable, BYOK.

- Repo: https://github.com/kinkos1234/thegongsi
- Live: https://thegongsi.vercel.app

---

## 핵심 기능 3가지

**1. 이상 공시 자동 플래그 (High/Med/Low/Uncertain)**

11개 룰 키워드(상장폐지, 감사거절, 최대주주 변경, 횡령·배임 등) 1차 필터 + Claude Haiku 심각도 분류기 2차 검증. 루틴(정기보고서, 배당결정 등)은 자동 제외.

현재 966건 중 89건이 high/med/uncertain 플래그됨.

**2. DD 메모 (Bull / Bear / Thesis)**

Fey editorial 톤을 벤치마크. 3-column이 아니라 **BULL·BEAR 상단 2-col + THESIS 하단 전체너비** 레이아웃. LLM이 생성한 뒤 citation validator + forbidden-words 가드를 2회 retry.

**3. GraphRAG 자연어 질의**

"HBM 공급망 중 최근 이상 공시 있는 회사?" 같은 다단계 질의를 Cypher + 키워드 검색 + 회사 검색 tool call 조합으로 처리.

---

## 스택

```
Frontend:  Next.js 16 (App Router) + Tailwind 4 + Recharts 3
Backend:   FastAPI 0.115 + SQLAlchemy 2.0 async + dart-fss + Anthropic SDK
Graph:     Neo4j 5 (Company · Disclosure · TimePoint 3개 노드 타입)
Infra:     Docker compose (로컬) / Vercel + Fly.io + AuraDB + Supabase ($0/월)
LLM:       Claude Sonnet 4.6 (메모·QA) + Haiku 4.5 (분류)
```

---

## 결정 1: pgvector·SBERT를 버렸다

처음엔 교과서처럼 갔다. SBERT로 공시 요약 임베딩 → pgvector HNSW 인덱스 → 의미 검색. 동작은 한다.

문제는:
- 임베딩 모델이 한국 금융 도메인에 약함 (특히 약칭·티커·계약명)
- "HBM 공급망" 같은 **개념적 다단계 질의**는 벡터 유사도로 안 됨
- 인프라 부담 (pgvector 확장 + 배치 재임베딩)

대안으로 Claude의 **tool_use agentic loop**로 대체했다. 3개 툴을 줬다:

```python
TOOLS = [
    {"name": "run_cypher", ...},        # Neo4j 그래프 질의
    {"name": "search_disclosures", ...}, # 공시 키워드 검색
    {"name": "search_companies", ...},   # 회사명/섹터 검색
]
```

`max_hops=6`, `max_total_calls=8` 상한으로 폭주 방지. 모델이 스스로 "회사 먼저 찾고 → 그 회사의 공시 그래프 타고 → 이상 severity 필터" 순서를 결정한다.

**벤치 결과 (v0.1, 8개 쿼리)**:
- Before (pgvector + SBERT): recall 0.75, precision 0.71
- After (Claude multi-tool): **recall 1.0, precision 1.0**

pgvector 종속성 전부 제거. requirements.txt 5줄 줄어들고 Docker 이미지 70MB 작아졌다.

---

## 결정 2: Neo4j를 GraphRAG 1급 시민으로

처음엔 Postgres만으로 충분하다고 생각했다. 관계는 조인하면 되니까.

바뀐 이유는 **시간 차원** 때문이다. "삼성전자가 2025년 3분기에 발생한 최대주주 변경 공시와 같은 분기에 HBM 공급망 핵심사가 공시한 것들" 같은 질의는 SQL로 짜면 지옥이다. Neo4j에 `(Disclosure)-[:OCCURRED_AT]->(TimePoint {year, quarter})` 로 박으면 Cypher 3줄.

```cypher
MATCH (c:Company {ticker: '005930'})<-[:FILED_BY]-(d:Disclosure)-[:OCCURRED_AT]->(tp:TimePoint)
WHERE tp.quarter = '2025Q3' AND d.severity IN ['high', 'med']
MATCH (tp)<-[:OCCURRED_AT]-(d2:Disclosure)-[:FILED_BY]->(c2:Company)
WHERE c2.sector = '반도체' AND c2.ticker <> c.ticker
RETURN c2.name_ko, d2.report_nm, d.reason
```

Postgres(SQLite/Supabase)는 **원천 데이터** (User, Disclosure raw, DDMemo), Neo4j는 **탐사 질의**. 역할 분리.

Cypher 인젝션 방어는 `re.IGNORECASE` 정규식 + 단어 경계 `\b`로 `CREATE|MERGE|DELETE|SET|REMOVE|DROP|CALL|LOAD|FOREACH` 차단 + 서버 레벨 `read_only=True` 세션 2중 방어.

---

## 결정 3: BYOK 3-tier

LLM 비용 폭주가 제일 무서웠다. 공개 데모에 `ANTHROPIC_API_KEY` 한 개 박아두면 하루 만에 $$$ 나갈 수 있다.

```
1. 사용자 BYOK (Fernet 암호화 DB 저장)  → 쿼터 무제한
2. 서버 fallback 키 (ADMIN_EMAILS만)    → 일일 memo 3 / ask 20
3. 둘 다 없음                           → 503
```

쿼터 카운팅은 원자적 UPDATE로 레이스 컨디션 방지:

```python
result = await db.execute(
    update(ServerKeyUsage)
    .where(..., ServerKeyUsage.count < limit)
    .values(count=ServerKeyUsage.count + 1)
)
```

`rowcount == 0` 이면 한도 초과로 차단.

---

## 안 한 것 / 포기한 것

- **실시간 스트리밍 가격**: yfinance로 daily close만. 실시간은 제휴 비용이 커서 연기
- **커뮤니티 댓글**: 모더레이션 부담 → feedback 버튼(up/down)만
- **모바일 네이티브 앱**: 웹 반응형으로 충분 (햄버거 메뉴까지만)
- **pgvector 재복귀 유혹**: 성능 벤치 유지되는 한 돌아가지 않기로

---

## 열어둔 것

- 지배구조 보고서 문서 fetch → 인물 entity extraction (Phase 2)
- Weekly benchmark 자동 리포팅
- DART 외 다른 규제당국(SEC, FSA) 커넥터

---

## 써보기

**로컬**:
```bash
git clone https://github.com/kinkos1234/thegongsi
cd thegongsi
docker compose up -d
# frontend는 http://localhost:3333
# backend는 http://localhost:8888/docs
```

**라이브** (알파): https://thegongsi.vercel.app

`/ask` QA 기능은 로그인 후 `/settings`에서 본인 Anthropic 키(BYOK) 등록이 필요합니다. 키는 Fernet로 DB에 암호화 저장되고, `/settings`에서 언제든 삭제 가능.

---

## 부탁

- 깃허브 ★ 하나와 이슈·PR 환영입니다
- 특히 **한국 개발자·투자자의 톤/UX 피드백**이 필요해요
- "이런 공시 감지 룰이 빠졌다" / "그래프 질의 이런 게 하고 싶다" 라는 제보면 최고

---

**MIT · BYOK · self-hostable.**
Fey처럼 아름답게, Hindenburg처럼 날카롭게, 한국 공시 맥락으로.

— _made by kinkos1234, with Claude_
