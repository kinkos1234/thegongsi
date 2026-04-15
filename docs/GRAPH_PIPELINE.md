# Graph Auto-Fill Pipeline (P1-7)

**목표:** KOSPI/KOSDAQ 2,600개 상장사 × 평균 20 관계 = **목표 5만 엣지**
**moat:** UI/LLM은 복제 가능. Proprietary **기업 관계 그래프 품질**이 comad-stock의 진입장벽.

## 원칙 (Hassabis + Bush)

1. **구조화된 데이터부터** — DART/공정위/한국신용정보처럼 스키마가 있는 공식 소스 우선.
2. **LLM은 NER/relation extraction에만 쓴다** — 내러티브 생성은 부차적.
3. **Provenance 필수** — 모든 엣지는 `source` + `extracted_at` + `confidence` 속성 포함.
4. **TimePoint 노드** — `since: "2020"` 같은 엣지 property 대신 `(e)-[:ACTIVE_IN]->(:TimePoint {year, quarter})`.
5. **Benchmark 중심 진화** — 100개 gold-standard query로 recall/precision 추적.

## 데이터 소스 매트릭스

| 소스 | 관계 | 접근 | 난이도 | 우선순위 |
|---|---|---|---|---|
| DART 지배구조 보고서 | OWNS, LEADS, HOLDS | dart-fss API | ★★ | P0 |
| DART 사업보고서 - 종속·관계회사 | OWNS | dart-fss 표 파싱 | ★★ | P0 |
| DART 감사보고서 주석 | SUPPLIES (주요 매입처/매출처) | PDF → LLM NER | ★★★ | P1 |
| 공정위 대규모기업집단 공시 | OWNS, GROUP_OF | OpenAPI, CSV | ★★ | P0 |
| 한국신용정보 기업정보 API | SUPPLIES, COMPETES_WITH | 유료 API | ★ | P2 |
| 뉴스 본문 (한경·매경 RSS + 본문) | COMPETES_WITH, SUPPLIES, PARTNERS | RSS + trafilatura + LLM | ★★★★ | P2 |
| 증권사 리서치 리포트 PDF | SUPPLIES 체인 | PDF scraper + LLM | ★★★★★ | P3 |

## Phase 1 MVP 파이프라인 (3주 예상)

### Week 1 — DART 지배구조 수집기
```
dart.get_report('지배구조보고서') per corp_code
  → HTML table 파싱 (pandas.read_html)
  → 임원 목록 → (:Person)
  → 대주주 목록 → (:Person)-[:HOLDS {pct, as_of}]->(:Company)
  → 최대주주 → (:Person|Company)-[:OWNS {pct}]->(:Company)
```
**산출물:** 2,600 회사 × 평균 8 인물/지분 = **~20,000 엣지**

### Week 2 — 공정위 대규모기업집단
```
ftc.go.kr API → 기업집단 82개 + 소속사 6,000+
  → (:Group)-[:HAS]->(:Company)
  → 동일 그룹 회사 간 (:Company)-[:GROUP_OF]->(:Company)
  → 총수 → (:Person)-[:LEADS]->(:Group)
```
**산출물:** ~8,000 엣지

### Week 3 — DART 종속·관계회사 (연결재무제표 주석)
```
dart.extract('연결재무제표 주석', item='종속회사')
  → 자회사 목록 파싱
  → (:Company)-[:OWNS {pct, scope: "subsidiary"}]->(:Company)
```
**산출물:** ~10,000 엣지

**3주 합계: ~38,000 엣지** (목표 5만의 76%)

## Phase 2 — LLM NER (뉴스·리포트)

### 파이프라인
```
뉴스 본문 (1만건/월) →
  청크 1500자 →
  Claude Haiku (structured output):
    {
      subject: { name, type: "Company" },
      predicate: "SUPPLIES" | "COMPETES_WITH" | "PARTNERS",
      object: { name, type: "Company" },
      evidence_span: "...",
      confidence: 0.0~1.0
    }
  → entity resolution (ticker 매핑)
  → confidence ≥ 0.7만 Neo4j upsert
```

### 중복·충돌 해결
- Entity canonicalization: `name_ko` + `ticker` 이중 해시
- Relation merge: 같은 subject-predicate-object가 여러 번 → `sources.append()`, `confidence = max()`
- 시간 정보: 뉴스 발행일을 `since: YYYY-MM`으로 마킹

## 벤치마크 Suite (AlphaFold-style)

`bench/queries.yml` — 100개 gold query.
```yaml
- id: hbm-supply-2024
  question: "2024년 HBM 공급망에 속한 회사"
  expected_companies: [005930, 000660, 042700, 036490, ...]
  min_recall: 0.8
  min_precision: 0.7
- id: samsung-subsidiaries
  question: "삼성전자 자회사"
  expected_companies: [028050, 006400, 009150, ...]
- ...
```

### 측정
```bash
python scripts/bench.py
# → bench_results/2026-04-15.json
#    overall recall: 0.73 / precision: 0.81 / per-query breakdown
```
릴리스마다 regression check, 기울기 하락 시 merge 차단.

## 데이터 모델 확장

기존 `Company`/`Person`에 더해:
```python
class Edge(Base):
    """관계형 DB에 Neo4j 엣지 복사본 (감사·검색용)."""
    source_type, source_id  # Company|Person
    predicate               # OWNS, SUPPLIES, ...
    target_type, target_id
    confidence: float
    source: str             # 'dart:rcept_no=...' | 'ftc:2026Q1' | 'news:url'
    valid_from: date | null
    valid_to: date | null
    extracted_at: datetime
```

## 실행 순서 (DART 키 도착 후)

1. `scripts/dart_corp_codes.py` — 2,600 corp_code 목록 동기화
2. `scripts/extract_governance.py` — 지배구조 보고서 10건씩 루프 (rate limit 주의)
3. `scripts/extract_ftc_groups.py` — 공정위 그룹 일괄
4. `scripts/extract_subsidiaries.py` — 연결재무제표 주석
5. `scripts/bench.py` — 초기 recall/precision 측정, baseline 저장
6. Phase 2 LLM NER 파이프라인 이후 매주 bench 재측정

## 법적/윤리 고려

- DART: 공공데이터, 재배포 가능. `source: "dart:rcept_no"` 명시.
- 공정위: 공공데이터, 동일.
- 뉴스 본문: 저작권 제한 — **추출된 관계만** 저장, 본문은 URL 링크로만.
- 한신정: 유료, ToS 확인 후 계약. Phase 2+.

## 성공 기준

- **12주차:** 3만 엣지 + bench recall 0.6
- **24주차:** 5만 엣지 + bench recall 0.75
- **52주차:** 10만 엣지 + bench recall 0.85 → 실제 moat 확립
