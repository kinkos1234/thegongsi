# Changelog

All notable changes to The Gongsi are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/),
dates in local 2026 Asia/Seoul.

---

## [0.3.0] — 2026-04-19

### Added — 지배구조 렌즈 + Editorial UI

- **지배구조 파이프라인** — 3 tables (`major_shareholders` · `insiders` ·
  `corporate_ownership`) + Neo4j `HOLDS_SHARES` Company→Company edge.
  `extractor.py` tool schema에 `corporate_shareholders[]` · `classification` ·
  `is_registered` 필드 추가. dialect-neutral upsert (`pg_insert` / `sqlite_insert`
  + `on_conflict_do_update`) — idempotent re-extraction.
- **순환출자 DFS 감지** — `governance_query.detect_circular_ownership_sql`,
  max_depth 5. 삼성전자 005930 → 006400 → 028260 → 032830 → 005930 데모 seed
  (`scripts/seed_governance.py`).
- **OwnershipDendrogram** — 가로 parent·self·child 가지 SVG. 5라운드 감사에서
  텍스트 overlap 지적 받고 rowHeight 28→52px · viewBox 640→680 · center box
  100×28→112×32로 수정. 모바일 뷰포트는 수직 화살표 리스트로 대체.
- **GovernanceBlock** — `buildNarrative(d)`가 오너 직접%·법인 간접%·기관%·
  cycles 수 집계 후 한 줄 요약. 순환출자 감지 시 sev-high 좌측 보더 블록.
- **RelatedCompanies** — 자체 force-directed physics (spring + Coulomb +
  damping, 3s auto-stop, requestAnimationFrame). SVG arrow marker 로 parent→
  center 방향 표시. 릴레이션 pill([모기업]/[자회사]/[섹터]). d3 의존성 없음.
- **PulseRibbon** — `/api/stats/pulse?days=N` 최근 N일 high+med 일별 카운트.
  80px 리본, 점선 평균선, accent today marker, sev-high peak marker, 3-point
  축 라벨(시작일·max·오늘).
- **CoverageStats** — `/api/stats/coverage` 총 공시·커버 기업·7d 이상 공시·since·
  daily_avg. 랜딩 트러스트 시그널.
- **EditorialMasthead** — `VOL.YYYY · Wxx · KST timestamp · 7d 이상 N건 ·
  dart-native · editorial`. ISO week 계산, 1분 주기 tick.
- **ConventionOnboarding** — 첫 방문 시 KR(빨강 상승)/US(초록 상승) 가격 색상
  관습 선택 배너. ESC로 닫힘, `data-convention` 속성 저장, `useCallback` +
  `useRef` 포커스 복구.
- **LoginGate 공통 컴포넌트** — settings/watchlist 가드 페이지 상단 여백
  문제(전체 감사에서 발견) 해결. `min-h-[calc(100vh-200px)] flex items-center`
  수직 중앙 배치 + accent 좌측 보더 카드.
- **Ask 비로그인 티저** — 기존 `/login` 즉시 redirect 제거. 비로그인 상태도
  질의 입력창 + 5개 예시 렌더, 버튼 라벨 `login & ask →`로 변경.
- **`icon.tsx` + `apple-icon.tsx`** — Next.js 16 `ImageResponse`로 동적 생성.
  32×32 (accent G) · 180×180 (G + GONGSI). favicon.ico 404 issue 해결.
- **무료 한국어 에디토리얼 폰트 스택** — Pretendard Variable (CDN) · Hahmlet
  (Korean editorial serif, OFL) · Gowun Batang (fallback) · EB Garamond ·
  JetBrains Mono. 유료 폰트(Paperlogy/산돌) 전면 제거.
- **`/api/stats/ask-suggestions`** — 최근 high+med 공시의 섹터·키워드로 동적
  질의 제안 3-5개 + fallback.
- **Convention CSS 오버라이드** — `html[data-convention="kr"]` 에서 `.price-up`
  이 sev-high(red) 적용, 하락이 blue(#60A5FA). 가격·Sparkline 일관 적용.

### Fixed

- **`rcept_dt` 날짜 포맷 일치** — stats 엔드포인트가 `strftime("%Y%m%d")`로
  cutoff 계산했는데 DB는 `YYYY-MM-DD` 저장이라 PulseRibbon + anomalies_7d가
  0 반환. `.date().isoformat()` 기반으로 수정.
- **OwnershipDendrogram 텍스트 overlap** — 5라운드 감사에서 "지분관계그래프
  텍스트 겹친다" 제보 받고 rowHeight 2배 + path curve 조정으로 해결.

## [Unreleased]

### Added (2026-04-18 오후 — v0.2.0 태그 이후)

- **공급망 그래프 구축** (seed v1→v5) — 41 categories / 187 SUPPLIES edges.
  HBM · 2차전지 · 자동차 · 반도체소재 · 방산 · 조선 · 통신 · 건설 · 화장품 ·
  금융 · 보험 · 해운 · 교육 · 의료기기 · IT 서비스 · 보안 등 국내 주요 산업
  대부분 커버. `backend/data/supply_chains.yaml` + `scripts/seed_supply_chains.py`.
- **LLM 공급망 추출기** (`supply_chain_extractor.py`) — DART document.xml 본문
  fetch → HTML 태그 제거 → Claude Haiku 로 4종 관계(SUPPLIES/OWNS/
  COMPETES_WITH/PARTNERS) 추출. confidence<0.6 · ticker 매칭 실패는 버림.
  매주 cron 으로 누적. admin_jobs `extract_supply_chains` 엔드포인트.
- **Discord Embed 알림** (admin 글로벌 webhook) — severity 이모지(🔴🟡🔵⚪)
  + 종목명(ticker) + DART 원문 링크 + 더공시 종목 페이지 링크. high severity
  만 broadcast (rate limit 보호 + 노이즈 방지). `check_and_alert` 가 user-level
  구독자(telegram/slack/discord BYOK)와 병행 디스패치.
- **keepalive workflow** — Fly API 10분 주기 + Neo4j graph_ping 6h 주기.
  무료 티어 idle-hibernate 예방으로 첫 방문자 콜드 스타트 10-60s → 400ms.
- **RecentEarnings** widget on landing — Q1 2026 잠정실적 Top 5 with 조/억/백만원
  human-readable formatting.
- **종목명 JOIN** — `/api/earnings/` Company LEFT JOIN 으로 `name_ko` 반환.
  프론트/Discord Embed 모두 "LG전자(066570)" 형태로 직관화.
- **`loading.tsx` 3종** — `/c/[ticker]` · `/watchlist` · `/settings` 에 Next.js
  App Router Suspense 스켈레톤. 2.2s SSR 대기 UX 개선.

### Fixed (2026-04-18 오후)

- **AlertConfig stale 레코드로 인한 DNS 실패** — DB의 `target='https://hook'`
  1건이 `send_discord` 호출 시 httpx DNS 실패로 전체 alert 파이프라인 crash
  시키던 문제. `send_*` 함수에 try/except + 10s timeout 추가. 라우터 POST
  단계에서 Discord/Slack/Telegram target prefix 포맷 검증 추가. 운영 DB
  에서 stale 1건 삭제.
- **버전 일관성** — `frontend/package.json` / `backend/app/main.py` FastAPI
  version / landing 라벨 모두 `0.2.0` 통일 (기존 0.1.0 stale).

### Added

### Fixed

- **earnings 단위 혼재** — DART document.xml 의 `단위 :` 표기가 회사마다 다름
  (조원/억원/백만원). 모두 백만원 기준으로 정규화해 DB 컬럼 의미를 통일.
  Samsung 133 과 디오 41,307 을 같은 컬럼에서 비교 가능 (a5917f4).
- **earnings 당해실적 앵커** — Samsung 식으로 xforms_input 이 컬럼 헤더로도
  쓰이는 양식에서 헤더를 실적값으로 오인하지 않도록 "당해실적" 앵커를
  먼저 찾고 그 뒤부터 값 검색 (a5917f4).
- **ex_dates_v2 파서 완전 재작성** — 유/무상증자결정 주요사항보고서의 실제
  양식이 `<TD>N. 라벨</TD><TU AUNITVALUE="YYYYMMDD">` 대문자+속성 기반
  이었는데 기존 parser 는 `<td>...<span class="xforms_input">` 소문자
  가정이라 한 건도 매치 안 됨. TD/TU 신양식 regex + legacy fallback
  으로 재작성 → 85 filings → 159 events (732bbf5).
- **admin_jobs 동기 응답** — 이전 BackgroundTasks 방식은 HTTP 응답 즉시
  반환 후 subprocess 가 백그라운드에서 돌았는데, Fly 가 HTTP 요청이
  끝난 것으로 보고 머신을 auto-stop 시켜 subprocess 가 중단되는 race.
  `asyncio.to_thread(subprocess.run, ...)` 로 subprocess 완료까지 HTTP
  응답을 대기시키는 방식으로 전환 (0c5b878).
- **admin_jobs 로그 마스킹** — stderr tail 에 `?crtfc_key=<평문>` 이 실려
  Actions 로그(public)로 유출 (2026-04-18 DART 키 사건). 정규식 기반
  `_mask_secrets` + FastAPI lifespan 에서 httpx/httpcore 로거 WARNING
  상향. 공용 헬퍼 `scripts/_logging_setup.py` 로 서브프로세스도 방어
  (fffb5e6, 038e00c).

### Infrastructure

- **GitHub Actions cron + Fly admin endpoint** — 이전 scheduler.py 는
  standalone 스크립트로 정의만 되어 있고 실제 프로덕션에서 한 번도 돌지
  않은 상태였음 (Dockerfile CMD 가 uvicorn 만 실행). Actions cron 이
  `POST /api/admin/jobs/{id}` 를 호출해 Fly 를 깨우고 subprocess 로 각
  수집 job 을 실행하는 구조 도입. `ADMIN_JOBS_TOKEN` + GitHub repo
  secrets 로 인증 (5cfbcec).

---

## [0.1.0] — 2026-04-15~17

초기 프로덕션 배포 + Threads 피드백 반영.

### Added

- DART-native 공시 수집 파이프라인 (OpenDART REST 직접 호출, dart-fss 제거).
- 종목 페이지 `/c/{ticker}` — Sparkline + TodayAnomalies + DD 메모 +
  DisclosureList + 공시 원문 프리뷰.
- `/ask` — GraphRAG multi-tool QA (run_cypher + search_disclosures +
  search_companies, max_hops=6).
- `/watchlist` — 종목 추가 시 DD 메모 + 권리락·배당락 자동 스캔.
- `/settings` — BYOK + admin 배지 + 쿼터 표시.
- 권리락·배당락 D-7 캘린더 (list.json v2 스캐너, 7,848 calls → ~10-50).
- 잠정/확정실적 공정공시 수집 (21 Q1 2026 rows).
- 주간 DB 백업 스크립트 (JSONL, 13 tables + optional S3).

### Fixed (Threads 피드백 5건 반영, 사이드 이슈 6건)

- 종목명 매칭, 과거 공시 검색, 권리락 캘린더, DD 메모 자동 생성,
  실적 캘린더. 28 커밋 / Fly 16 재배포.

### Infrastructure

- 15 석학 리뷰 23건 수정 (보안 9/10, 접근성 8/10, 총점 91/100).
- $0/월 스택 (Vercel Hobby + Fly.io Free + AuraDB Free + Supabase Free).
- GitHub public (MIT), CI: Python 3.12 + Node 20.

### Docs

- Velog 기술 장문 ("pgvector 를 버리고 Claude tool_use 로").
- Brunch 투자자용 장문 초안 (docs/launch/brunch-investor.md, 발행 대기).
