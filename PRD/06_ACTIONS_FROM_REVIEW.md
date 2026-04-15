# 06. 14인 석학 리뷰 통합 액션

**리뷰 일자:** 2026-04-15
**참가 페르소나:** Karpathy, Torvalds, Rams, Bach, House, PG, Bush, Amodei, Sutskever, LeCun, Hassabis, Altman, Dean, Fei-Fei Li

## 🔴 P0 — 런칭 전 필수

### 1. 팩트 검증 레이어
- [ ] DD 메모 각주 `rcept_no` 실제 DB 존재 검증 (post-hoc, 없으면 재생성)
- [ ] 메모 본문 금지어(`목표가/매수/추천`) 스캔 → 적중 시 재생성
- [ ] anomaly severity `uncertain` 4번째 옵션
- [ ] `DDMemoVersion` 감사 3튜플 `(user_id, key_owner, model)`

### 2. GraphRAG 안전 가드
- [ ] FORBIDDEN substring → Neo4j read-only 세션 전환
- [ ] 자유 Cypher → query-plan template 5~10종 + slot-filling
- [ ] `is_safe` false-positive(리터럴 'CREATE') 해결

### 3. `/c/[ticker]` 404 처리
- [ ] 존재하지 않는 ticker → 404 or 가까운 match

## 🟠 P1 — 정체성 확보

### 4. pgvector 실제 ingestion
- [ ] chunk_size 500 → 1500~2000자 + 문장 경계 overlap
- [ ] OpenAI embedding → pgvector 저장
- [ ] 차원 3072 → halfvec 2048 or matryoshka 1536
- [ ] `DDMemoVersion` 자체 embed → 버전 drift 시그널

### 5. 데이터·피드백 루프
- [ ] `DisclosureFeedback` 테이블
- [ ] `ReferenceSummary` 테이블
- [ ] UI 👍/👎 피드백 (`/c/[ticker]`, `/ask`)

### 6. 포지셔닝 재정의
- [ ] README 영문 TL;DR + "what is DART"
- [ ] counterintuitive 메시지 "공시 95%는 노이즈, 5%가 인생"
- [ ] B2B 리서처 타겟 + Phase 3 월 99~299만원
- [ ] 채널: 토스 피드, 디스콰이엇, 개미뉴스 카페

### 7. 그래프 자동 채움
- [ ] DART 지배구조 보고서 entity extraction
- [ ] 공정위 대규모기업집단 지분 관계
- [ ] `(:TimePoint)` 시간 노드 도입
- [ ] 목표 5만 엣지

## 🟡 P2 — 품질·성숙도

### 8. 테스트 확장
- [ ] yfinance fallback 유닛 테스트
- [ ] pgvector ingest 실패 경로
- [ ] Neo4j seed idempotent
- [ ] /ask e2e (빈값·Cmd+Enter)

### 9. 코드 구조
- [ ] `models/tables.py` → `{user, market, signals, memo, feedback}.py` 5분할
- [ ] `collect_all` → asyncio.Queue + retry 래퍼
- [ ] config read-only/rotatable 분리
- [ ] LLM structured output 전환

### 10. 디자인 detail
- [ ] DDMemoCard THESIS serif 확대, BULL/BEAR side-by-side
- [ ] 랜딩 2nd 섹션 tracking 제거
- [ ] 라이트 accent `#15803D` (WCAG AA)
- [ ] font-size 4종 이하 수렴

## 🟢 P3 — 인프라·스케일 (Phase 2+)

### 11. Infra
- [ ] `_cache` → Redis
- [ ] Neo4j HA/cluster
- [ ] yfinance → Kiwoom/Polygon migration path
- [ ] DART federated collection
- [ ] Anthropic tier 4+ 계약

### 12. Benchmark suite
- [ ] `bench/` 100 query + ground truth
- [ ] recall/precision 자동 측정
- [ ] 릴리스 regression check

## 🎯 가장 urgent 5개

| # | 액션 | 리뷰어 | 영향 |
|---|---|---|---|
| 1 | 각주 fabrication validator | LeCun·Amodei·Bach | 신뢰성 근본 |
| 2 | pgvector 실제 ingestion | Sutskever·Hassabis | 반쪽 제품 완성 |
| 3 | `/c/[ticker]` 404 | Bach | 블로커 |
| 4 | 그래프 자동 채움 | Hassabis·Bush | moat 형성 |
| 5 | 포지셔닝 재정의 + 영문 요약 | PG·Altman | 런칭 성공률 |

## 스코어카드 (실행 전후)

| 축 | 현재 | urgent 5 완료 | 예상 소요 |
|---|---|---|---|
| Safety | 2/5 | 4/5 | 4h |
| Factuality | 1/5 | 4/5 | 6h |
| Representation | 2/5 | 4/5 | 8h |
| Moat | 2/5 | 3/5 | 16h (진짜 3은 5만 엣지 시점) |
| Design | 4/5 | 4/5 | 2h |
| Distribution | 1/5 | 3/5 | 2h |
| Infra | 3/5 | 3/5 | Phase 2 |

**런칭 판단:** P0 + urgent 5 완료 → Show HN 가능.
