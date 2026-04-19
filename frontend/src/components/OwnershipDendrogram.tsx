"use client";

import Link from "next/link";

type Linked = {
  ticker: string;
  name: string | null;
  stake_pct: number | null;
  as_of: string;
};

/** 가로 덴드로그램 — parent · self · child 지배 형태 한 눈에.
 *
 * 왼쪽 부모들 → 중앙 self → 오른쪽 자식들. 각 가지에 지분율 라벨.
 * SVG 기반, 가지 개수에 따라 높이 동적 계산. 섹션 표지와 텍스트 병행 렌더.
 */
export function OwnershipDendrogram({
  center,
  centerName,
  parents,
  children,
}: {
  center: string;
  centerName: string | null;
  parents: Linked[];
  children: Linked[];
}) {
  const maxSide = Math.max(parents.length, children.length, 1);
  const rowHeight = 52; // 이름 + 상세 라인이 함께 들어가는 높이 (전 28 → 52)
  const height = Math.max(140, maxSide * rowHeight + 48);
  const width = 680;
  const midX = width / 2;
  const midY = height / 2;
  const branchLen = 200;
  const parentX = midX - branchLen;
  const childX = midX + branchLen;

  function yAt(index: number, total: number) {
    if (total <= 1) return midY;
    const spread = (total - 1) * rowHeight;
    const startY = midY - spread / 2;
    return startY + index * rowHeight;
  }

  const hasData = parents.length > 0 || children.length > 0;
  if (!hasData) return null;

  return (
    <div className="mt-8">
      <h3 className="mono text-[11px] text-fg-3 uppercase tracking-[0.15em] mb-4">
        지배 구조 — 가지 그래프
      </h3>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full max-w-full text-fg-3"
        role="img"
        aria-label={`${centerName ?? center} 모기업 ${parents.length}곳, 자회사 ${children.length}곳`}
      >
        {/* parent branches — 왼쪽에서 중앙으로 */}
        {parents.map((p, i) => {
          const py = yAt(i, parents.length);
          const textStartX = parentX;
          // 곡선 연결선: 피어 위치(py) → 중간 구간 → 중앙 self
          const connectorStart = textStartX + 140; // 텍스트 영역 오른쪽 끝
          return (
            <g key={`p-${p.ticker}`}>
              <path
                d={`M ${connectorStart} ${py} L ${midX - 80} ${py} Q ${midX - 40} ${py}, ${midX - 40} ${midY} L ${midX - 56} ${midY}`}
                stroke="currentColor"
                strokeOpacity="0.5"
                strokeWidth="1.25"
                fill="none"
              />
              <text
                x={textStartX}
                y={py - 6}
                className="fill-[var(--color-fg)]"
                style={{ fontFamily: "var(--font-sans)", fontSize: 12 }}
              >
                {p.name ?? p.ticker}
              </text>
              <text
                x={textStartX}
                y={py + 12}
                className="fill-[var(--color-fg-3)]"
                style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}
              >
                {p.ticker}
                {p.stake_pct != null ? ` · ${p.stake_pct.toFixed(2)}%` : ""}
              </text>
            </g>
          );
        })}
        {/* child branches — 중앙에서 오른쪽으로 */}
        {children.map((c, i) => {
          const cy = yAt(i, children.length);
          const textStartX = childX - 140;
          const connectorEnd = textStartX;
          return (
            <g key={`c-${c.ticker}`}>
              <path
                d={`M ${midX + 56} ${midY} L ${midX + 40} ${midY} Q ${midX + 40} ${cy}, ${midX + 80} ${cy} L ${connectorEnd} ${cy}`}
                stroke="currentColor"
                strokeOpacity="0.5"
                strokeWidth="1.25"
                fill="none"
              />
              <text
                x={textStartX}
                y={cy - 6}
                className="fill-[var(--color-fg)]"
                style={{ fontFamily: "var(--font-sans)", fontSize: 12 }}
              >
                {c.name ?? c.ticker}
              </text>
              <text
                x={textStartX}
                y={cy + 12}
                className="fill-[var(--color-fg-3)]"
                style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}
              >
                {c.ticker}
                {c.stake_pct != null ? ` · ${c.stake_pct.toFixed(2)}%` : ""}
              </text>
            </g>
          );
        })}
        {/* center 노드 — 크기 키우고 중앙 텍스트 정확히 정렬 */}
        <rect
          x={midX - 56}
          y={midY - 16}
          width="112"
          height="32"
          fill="var(--color-bg-2)"
          stroke="var(--color-accent)"
          strokeWidth="1.5"
        />
        <text
          x={midX}
          y={midY + 5}
          textAnchor="middle"
          className="fill-[var(--color-fg)]"
          style={{ fontFamily: "var(--font-serif)", fontSize: 14 }}
        >
          {centerName ?? center}
        </text>
        {/* 헤더 라벨 */}
        <text
          x={parentX}
          y={16}
          className="fill-[var(--color-fg-3)]"
          style={{ fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.12em" }}
        >
          PARENTS ({parents.length})
        </text>
        <text
          x={childX}
          y={16}
          textAnchor="end"
          className="fill-[var(--color-fg-3)]"
          style={{ fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.12em" }}
        >
          CHILDREN ({children.length})
        </text>
      </svg>

      <ul className="md:hidden mt-2 divide-y divide-border/40">
        {/* 모바일 대체 — SVG 가지가 좁은 폭에서 읽기 어려울 때 텍스트 리스트 */}
        {parents.map((p) => (
          <li key={`pm-${p.ticker}`} className="py-1.5 text-[12px] text-fg-2 flex gap-2">
            <span className="text-fg-3">←</span>
            <Link href={`/c/${p.ticker}`} className="hover:text-accent">
              {p.name ?? p.ticker}
            </Link>
            {p.stake_pct != null && (
              <span className="mono text-fg-3">{p.stake_pct.toFixed(2)}%</span>
            )}
          </li>
        ))}
        {children.map((c) => (
          <li key={`cm-${c.ticker}`} className="py-1.5 text-[12px] text-fg-2 flex gap-2">
            <span className="text-fg-3">→</span>
            <Link href={`/c/${c.ticker}`} className="hover:text-accent">
              {c.name ?? c.ticker}
            </Link>
            {c.stake_pct != null && (
              <span className="mono text-fg-3">{c.stake_pct.toFixed(2)}%</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
