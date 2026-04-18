# Changelog

All notable changes to The Gongsi are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/),
dates in local 2026 Asia/Seoul.

---

## [Unreleased]

### Added

- **RecentEarnings** widget on landing — Q1 2026 잠정실적 Top 5 with 조/억/백만원
  human-readable formatting.

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
