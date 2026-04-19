/** 더공시 심볼 — 공시문서(DART 표) 조형 + ㄱ 자소 + 플래그 점.
 *
 * - 좌상단 꺾쇠(ㄱ)는 문서 모서리이자 한글 자소
 * - 2개의 가로줄은 공시 표의 행
 * - 우상단 accent 점은 "이상 공시 플래그"
 * - 전체 12px 그리드에 스냅, 1.25px stroke(높은 DPR에서 선명)
 */
export function BrandMark({
  size = 16,
  className = "",
  flagged = true,
}: {
  size?: number;
  className?: string;
  flagged?: boolean;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      role="img"
      aria-label="The Gongsi"
      className={className}
    >
      {/* 문서 베이스 — 오른쪽 아래 열린 ㄱ 조형 */}
      <path
        d="M4 4 H20 V20 H4 Z"
        stroke="currentColor"
        strokeOpacity="0.22"
        strokeWidth="1.25"
      />
      {/* ㄱ 자소 — 두꺼운 strike + 세리프 foot */}
      <path
        d="M4 4 H14 M4 4 V14 M14 4 V6.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="square"
      />
      {/* ㄱ 세리프 foot (아래 짧은 가로) */}
      <path
        d="M2.5 14 H5.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="square"
      />
      {/* 표 행 2개 — 공시 데이터 리듬 */}
      <path
        d="M7 17 H17 M10 20 H17"
        stroke="currentColor"
        strokeOpacity="0.55"
        strokeWidth="1.25"
        strokeLinecap="square"
      />
      {/* 플래그 점 — 이상 공시 시그널 */}
      {flagged && (
        <circle cx="19" cy="5" r="1.8" fill="var(--color-accent)" />
      )}
    </svg>
  );
}
