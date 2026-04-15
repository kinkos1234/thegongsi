# Demo Assets

런칭 포스팅(Show HN, dev.to, 토스 피드, 디스콰이엇)을 위한 스크린샷·영상 가이드.

## 자동 캡처 스크립트

`docs/scripts/capture_demo.mjs` — Playwright 기반, 7컷 자동 촬영.

### 셋업
```bash
cd docs
npm install playwright
npx playwright install chromium
```

### 촬영 대상
| 파일 | 경로 | 상태 |
|---|---|---|
| `01-landing.png` | `/` | Hero + "왜 DART인가" + footer (1440×full) |
| `02-login.png` | `/login` | 로그인 폼 |
| `03-ask-empty.png` | `/ask` | Q&A 입력만 |
| `04-ask-answer.png` | `/ask` | "이재용이 이끄는 회사" 답변 렌더 |
| `05-company-dashboard.png` | `/c/005930` | CompanyHeader + Sparkline + Disclosures + DDMemoCard |
| `06-404.png` | `/c/000000` | 편집자 404 화면 |
| `07-watchlist-empty.png` | `/watchlist` | 비어있는 EmptyState |

### 실행
```bash
# 별도 터미널에서 backend + frontend 띄운 상태로
node docs/scripts/capture_demo.mjs
```
→ `docs/screenshots/*.png`

## 포스팅용 헤더 이미지 (1200×630)

`01-landing.png`에서 상단 720×630 crop → SNS 카드에 최적. 또는 Figma로 별도 제작:

- 타이틀: "한국 주식, 진지한 리서치로"
- 서브: "DART-native AI research terminal · OSS"
- 비주얼: Sparkline 한 줄 + DD 메모 bullet 3개

## 영상 (선택)

30초 루프, 자막 영어. 구간:
1. 랜딩 스크롤 (5s)
2. 종목 검색 → 대시보드 (10s)
3. `/ask` 질문 → 답변 (10s)
4. 다크→라이트 토글 (5s)

도구: Kap (mac), OBS, 또는 Playwright `page.video()`.

## 체크리스트 (포스팅 전)

- [ ] 모든 스크린샷 1440×≥900, retina 2x
- [ ] 개인 정보 없음 (이메일, 토큰)
- [ ] 실공시 데이터 로드된 `/c/005930` 스크린샷 (DART 키 확보 후)
- [ ] 영문 TL;DR README 최종 교정
- [ ] `04-ask-answer` 답변이 citation 포함
