# Launch Checklist — The Gongsi

**Target**: Soft launch via GitHub public + Show HN + dev.to + KR 한국어 채널

## ✅ D-0 (런칭 당일) 체크리스트

### 코드 품질
- [x] pytest 30/30 pass
- [x] bench v0.1 8/8 pass (recall 1.0, precision 1.0)
- [x] lint typecheck 무검수 (로컬) — CI에서 최종
- [x] 39 git commits cleanly squashed? 필요 시 `git rebase -i --root` 정리 옵션

### 보안
- [x] `.env` gitignored
- [x] 커밋된 파일에 `sk-ant-*`, `sk-proj-*`, DART key 등 미노출 확인
- [x] Neo4j 비번은 `docker run` 명령 내부에만 (README에도 placeholder)
- [x] JWT secret 기본값은 dev용 표시

### 문서
- [x] `README.md` — 영문 TL;DR + 한국어 manifesto + 빠른 시작
- [x] `LICENSE` — MIT
- [x] `CONTRIBUTING.md`
- [x] `docs/DESIGN.md` — Fey 스타일 원칙
- [x] `docs/GRAPH_PIPELINE.md` — 5만 엣지 로드맵
- [x] `docs/DEMO_ASSETS.md` — Playwright 캡처 가이드
- [x] `docs/launch/show-hn.md` — Show HN 초안
- [x] `docs/launch/devto-ko.md` — dev.to 한국어 초안
- [x] `PRD/06_ACTIONS_FROM_REVIEW.md` — 14인 석학 리뷰

### 데모 자산
- [x] `docs/screenshots/` 9컷 Playwright 자동 캡처
- [x] 랜딩 + 삼성전자 대시보드 + 060240 스타코링크 실 데모

### GitHub 공개 준비
- [ ] **GitHub 저장소 이름 `thegongsi` 생성** (사용자 수행)
- [ ] 로컬 remote 설정: `git remote add origin https://github.com/USERNAME/thegongsi.git`
- [ ] `git push -u origin main`
- [ ] Social preview 이미지 업로드 (`docs/screenshots/01-landing.png` 상단 1200×630 crop)
- [ ] About 섹션 — "Korean disclosures, deciphered. DART + GraphRAG"
- [ ] Topics: `korea`, `dart`, `stock`, `finance`, `graphrag`, `nextjs`, `fastapi`, `neo4j`

### 최소 환경 변수 (README 확인)
```bash
# backend/.env
DATABASE_URL=sqlite+aiosqlite:///./the_gongsi.db
JWT_SECRET_KEY=<32+ bytes>
CORS_ORIGINS=http://localhost:3333
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<password>
DART_API_KEY=<OpenDART 발급>   # https://opendart.fss.or.kr
ANTHROPIC_API_KEY=<Claude key>  # https://console.anthropic.com

# optional
FIELD_ENCRYPTION_KEY=<Fernet 32 bytes>
TELEGRAM_BOT_TOKEN=
SLACK_WEBHOOK_URL=
DISCORD_WEBHOOK_URL=
```

## 📢 D-1 (런칭 +1일) 배포

### Show HN 포스팅
- 채널: https://news.ycombinator.com/submit
- 제목: `Show HN: The Gongsi – Open-source AI research terminal for Korean equities (DART + GraphRAG)`
- Body: `docs/launch/show-hn.md` 3-paragraph version
- 타이밍: **KR 화~목 아침 9~10시 (SF 전날 저녁 5~6시)** — 양 시장 동시 열림
- 포스팅 후 2-3 시간 댓글 응대 준비 (comment prep FAQ `docs/launch/show-hn.md` 참고)

### dev.to 크로스포스트
- 채널: https://dev.to/new
- 제목: `한국 주식을 위한 오픈소스 AI 리서치 터미널을 만들고 있습니다 — The Gongsi`
- Body: `docs/launch/devto-ko.md`
- 태그: `#opensource #korean #ai #rag #fintech`
- Cover: `docs/screenshots/01-landing.png` 상단 crop

### Tracking
- GitHub stars 시작값 기록
- HN 포지션/points 매 시간 스냅샷
- 댓글 감정 분석 (긍정/비판/질문 3분류)

## 📣 D-2~D+7 확장

### 한국 채널
- **토스 피드**: 앱 내 "글쓰기" — 종목 태그 삼성전자/SK하이닉스로 태깅
- **디스콰이엇**: "스타트업/개발자" 커뮤니티에 진행 상황 공유
- **개미뉴스 네이버 카페**: 가이드·사용법 포스트
- **GeekNews**: 기술 중심 투고 (영문 원글 + 한국어 요약)

### 피드백 루프
- `DisclosureFeedback`/`MemoFeedback` 엔드포인트 모니터링
- D+3: 첫 사용자 피드백 취합
- D+7: bench 재측정 + 리뷰어 석학 재평가

## 🧪 배포 후 검증

- [ ] **클린 clone 부트스트랩** — 새 머신에서 `git clone` → `scripts/bootstrap.py --seed` 8~10분 → 첫 방문 대시보드가 비어있지 않음 확인
- [ ] 배포 서버에서 `/api/health` 200
- [ ] `/ask` 한국어 질문 E2E 통과
- [ ] `/c/005930` 삼성 대시보드 렌더 확인
- [ ] DART 스케줄러 일일 배치 동작 확인 (KST 06:00)
- [ ] Anomaly severity 신규 공시 플래그 동작
- [ ] BYOK 기능 관리형 배포 시 활성

## 🚨 롤백 트리거

- pytest CI 실패
- 보안 인시던트 (API 키 노출, SQL 주입 등)
- Anthropic API rate-limit 에러 persistent
- Neo4j 데이터 손실

## 📊 성공 지표 (첫 30일)

- GitHub stars: **100+ target**
- HN top comment 건수: **5+** (의미있는 토론)
- 셀프호스팅 사용자 텔레메트리(opt-in): **20+**
- dev.to 조회수: **1,000+**
- 피드백 엔드포인트 신호: **50+** (DisclosureFeedback + MemoFeedback 합산)
- bench 재측정 유지: recall >= 0.9, precision >= 0.9
