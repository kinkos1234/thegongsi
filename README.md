# comad-stock

**DART-native AI 주식 리서치 터미널 — OSS, 한국어 우선.**

한국 리테일 투자자에게는 Fey/Seeking Alpha 수준의 진지한 리서치 도구가 없다. 네이버 증권은 광고+뉴스, 토스증권 인사이트는 단편적, 증권플러스는 가격 중심. 그 공백을 채우는 오픈소스 프로젝트.

## 상태

기획 단계 (2026-04-14 시작). comad-world 독립 자매 프로젝트.

## 두 가지 북극성

1. **기술적 완성도** — GraphRAG 기반 DART 공시 분석, 기업 엔티티 그래프, AI DD 메모 자동 생성. 단순 요약이 아닌 연결 추론.
2. **Fey급 UI/UX** — 광고 0, 정보 밀도와 심미성 동시 달성. 네이버 증권 UX를 두 세대 뛰어넘음.

## 3개 차별점

1. **DART 공시 AI 분석** — 반기/사업·주요사항·지분변동 자동 요약, 이상징후 감지.
2. **GraphRAG 엔티티 그래프** — 공급망·자회사·경쟁사·인물을 Neo4j에 구축. 자연어 Q&A.
3. **AI DD 메모 자동 생성** — 종목 입력 → bull/bear 한국어 메모(DART + 뉴스 + 실적 + 인사이더 통합).

## comad-world 재활용

- `comad-brain` → 금융 엔티티 GraphRAG (Neo4j)
- `comad-ear` → 공시/뉴스/실적 콜 수집
- `comad-eye` → DD 메모 생성 파이프라인

## 문서

- [research/market-landscape.md](research/market-landscape.md) — 시장 조사 (fey.com, 경쟁사 매트릭스, 포지셔닝 가설 4종)
- [docs/positioning.md](docs/positioning.md) — 확정 포지션 근거
- [docs/next-steps.md](docs/next-steps.md) — PRD 작성, 데이터 소스, 기술 스택

## 라이선스

MIT (예정).
