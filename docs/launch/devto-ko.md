# dev.to (한국어) 포스팅 초안

## 제목

**한국 주식을 위한 오픈소스 AI 리서치 터미널을 만들고 있습니다 — The Gongsi**

## Cover 이미지

`docs/screenshots/01-landing.png` 상단 1200×630 crop.

## 본문 (600단어 내)

한국 DIY 투자자에게는 Fey나 Seeking Alpha 수준의 진지한 리서치 도구가 없습니다. 네이버 증권은 광고+뉴스, 토스증권 인사이트는 단편적, 증권플러스는 가격 중심입니다. **그 공백을 채우려고 만들었습니다.**

### 문제

DART에는 연 100만건의 공시가 올라옵니다. 대부분은 루틴(보통주 주주총회 소집 같은)이지만, 그 5%가 투자 판단을 뒤집습니다 — 감사의견거절, 최대주주변경, 유상증자결정, 상장폐지 심사. 애널리스트는 이걸 수작업으로 스캔하고, 리테일은 대부분 놓칩니다.

### 접근

**(1) 규칙 + LLM 하이브리드 이상징후 탐지** — 11개 HIGH 키워드(상장폐지·감사거절 등) + 8개 MED 키워드로 1차 필터, Claude Haiku가 `high/med/low/uncertain` 판정. "uncertain"이 핵심: 애매한 건 human review 큐로.

**(2) GraphRAG 자연어 Q&A** — 공급망·경쟁사·인사 관계를 Neo4j에 저장. 질문이 들어오면 Claude가 Cypher 생성 → Neo4j **read-only 세션**으로 실행 → rows를 한국어 답변으로 합성 (2-hop). "이재용이 이끄는 회사?" → `MATCH (p:Person {name_ko: '이재용'})-[:LEADS]->(c:Company) RETURN c.name_ko` → "이재용은 삼성전자를 이끌고 있습니다."

**(3) AI DD 메모 with citation validator** — bull/bear/thesis 메모 자동 생성. 근데 LLM이 출처를 fabricate할 수 있어서, 생성 후 각주의 `rcept_no`가 실제 DB에 있는지 검증하고 없으면 재생성합니다. 이거 없으면 AI 리서치 도구가 아니라 creative writing tool이 됩니다.

### 스택

- Backend: FastAPI + SQLAlchemy 2.0 async + PostgreSQL(pgvector) + Neo4j 5
- Frontend: Next.js 16 App Router + Tailwind 4 + Recharts 3
- AI: Claude Haiku (anomaly + QA synth) + Sonnet (DD 메모)
- Infra: Docker Compose, BYOK (Fernet 암호화)
- pytest 34/34

### 왜 오픈소스

광고와 수수료 없이 한국 리테일에게 도구를 주는 방법입니다. 본인 API 키로 셀프호스팅 가능. Managed hosting은 Phase 2에 B2B (월 99~299만원)로만.

### 현 단계 & 로드맵

알파. 14인 AI 석학 리뷰(Karpathy, Rams, Sutskever, Amodei, LeCun, Altman, Fei-Fei Li…) 기반 로드맵:

- **P0 완료** — 팩트 검증 레이어, Neo4j read-only 가드, 404 처리
- **P1 진행 중** — pgvector ingestion, 5만 엣지 자동 채움 (DART 지배구조 + 공정위 + 종속회사)
- **P2+ 계획** — halfvec 2048 압축, benchmark suite, human-in-the-loop 피드백

### 피드백 받고 싶은 것

1. **그래프 품질** — KOSPI/KOSDAQ 2,600사 × 5종 관계 = 5만 엣지 목표. 어느 소스가 가장 신뢰할만한가요?
2. **guardrail 디자인** — Constitutional AI 스타일로 어디까지 해야 할까요?
3. **B2B vs B2C** — 개인 9,900원 vs 법인 99만원, 둘 다 갈까요?

GitHub: {TBD}
Design doc: docs/DESIGN.md (Fey-inspired editorial, dark-first)
Graph roadmap: docs/GRAPH_PIPELINE.md

#오픈소스 #한국주식 #AI #RAG #fintech
