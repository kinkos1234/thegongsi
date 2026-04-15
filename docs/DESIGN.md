# comad-stock Design System

**북극성:** Fey급 UI — 광고 0, 정보 밀도와 심미성 동시 달성. 네이버 증권 두 세대 도약.

## 1. 디자인 원칙

1. **Editorial over dashboard** — 트레이딩 터미널이 아닌 리서치 저널. 숫자는 차분하게, 텍스트는 신문처럼.
2. **Dark-first, monochrome + 1 accent** — 어두운 배경에 회색 계조 + 단일 액센트(상승 초록). 하락은 중성 빨강이 아닌 회색 처리(의미 과잉 경계).
3. **Typography-led hierarchy** — 크기·굵기·자간으로 계층 구조 표현. 박스·보더·그림자 최소화.
4. **Density without clutter** — 한 화면에 많이, 그러나 숨 쉬는 공간 유지. 8px 그리드 엄수.
5. **Korean-first typography** — 한국어 본문 최우선. Pretendard 본문 + Adelle/EB Garamond 디스플레이 혼식.

## 2. 컬러 토큰

```
--bg-primary     #0A0A0A   (거의 검정)
--bg-secondary   #141414   (카드·모듈)
--bg-tertiary    #1E1E1E   (호버·선택)
--border         #262626   (최소 사용)
--text-primary   #F5F5F5   (본문)
--text-secondary #A3A3A3   (보조)
--text-tertiary  #6B6B6B   (메타)
--accent         #4ADE80   (상승·액티브, green-400)
--accent-dim     #166534   (상승 배경)
--neutral-down   #A3A3A3   (하락 — 회색 처리)
--severity-high  #F87171   (이상징후 high만 예외)
--severity-med   #FBBF24
```

라이트 모드는 Phase 2. 한국 사용자 30%는 라이트 선호하지만 Fey 정체성 확립이 먼저.

## 3. 타이포그래피

| 용도 | Font | Size/Weight |
|---|---|---|
| Display (랜딩 헤로) | Adelle Sans · EB Garamond | 72/600, -2% |
| H1 (페이지 제목) | Pretendard | 40/600, -1% |
| H2 (섹션) | Pretendard | 24/500 |
| H3 (카드 제목) | Pretendard | 16/600 |
| Body | Pretendard | 15/400, line-height 1.6 |
| Small | Pretendard | 13/400 |
| Mono (숫자·티커·코드) | JetBrains Mono | tabular-nums, 14/500 |

원칙: **숫자는 전부 mono + tabular-nums**. 공시 제목은 본문 font지만 ticker는 mono로 즉각 식별.

## 4. 간격·레이아웃

- 8px grid. 컴포넌트 내부 padding: 16/24/32. 섹션 간격: 48/64/96.
- 최대 컨테이너 너비: 1280px (대시보드), 720px (리서치 리딩뷰).
- 반응형: 640(모바일) / 768(태블릿) / 1024(노트북) / 1440(데스크톱).

## 5. 핵심 컴포넌트

### CompanyHeader
- 종목명(한국어 Display) + 티커(Mono 작게) + 현재가 + 등락 한 줄.
- 아이콘·배지 없음. 여백으로 위계.

### DisclosureRow
- 날짜(mono tertiary) · 제목(body primary) · severity 점(6px 원, 색만).
- 호버 시 bg-tertiary. 클릭 시 원문 모달.

### DDMemoCard
- 상단: 버전 번호 + 생성 시각.
- 본문: `## BULL / ## BEAR / ## THESIS` 3단. 각주 pill로 출처 링크.
- 사이드: 이전 버전 diff (Phase 2).

### QAInput
- 풀 너비 입력. placeholder: "HBM 공급망에서 최근 이상 공시가 있는 회사?"
- 엔터 시 답변 스트리밍. Cypher는 접어서 노출(토글).

### TickerChart
- Recharts 3. 그리드·축·레전드 모두 가는 선(1px) tertiary 색.
- 상승 스파크는 accent, 하락은 neutral-down (회색).

## 6. 모션

- 200ms cubic-bezier(0.4, 0, 0.2, 1). 오버엔지니어 경계.
- 페이지 전환: fade + 8px slide. 카드 호버: border 없이 bg만 +10% 밝기.
- 숫자 카운트업 애니메이션은 쓰지 않음 (Fey 스타일 아님).

## 7. 안 쓰는 것

- 그림자(shadow-*), 라운드 과도한 값(rounded-xl 이상), 그라디언트, 이모지 UI.
- tooltip · popover의 말풍선 꼬리. 드롭다운 글라스모피즘.
- 네이버 증권식 컬러풀 배지.

## 8. 구현 스택

- Next.js 16 App Router + RSC
- Tailwind 4 (CSS 변수 네이티브)
- Recharts 3
- shadcn/ui는 **쓰지 않음** (프리미엄 감 해침) — 필요 컴포넌트만 직접 작성
- 아이콘: Lucide (최소 사용, 1.5px stroke)

## 9. 다음 단계

1. `app/globals.css` — 토큰 정의
2. `app/layout.tsx` — 기본 레이아웃
3. `app/page.tsx` — 랜딩 (디자인 검증용)
4. `components/CompanyHeader.tsx` + `DisclosureRow.tsx` + `DDMemoCard.tsx` 프로토타입
5. 실제 더미 데이터로 대시보드 1화면 완성 → 스크린샷으로 디자인 승인
