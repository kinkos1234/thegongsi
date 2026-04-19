"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type Relation = "parent" | "child" | "sector" | "supplier" | "competitor";

type Peer = {
  ticker: string;
  name: string | null;
  sector: string | null;
  change: number | null;
  relation?: Relation;
  stake_pct?: number | null;
  direction?: "in" | "out";
};

type Response = {
  center: Peer;
  relation: string;
  relations?: Record<string, number>;
  peers: Peer[];
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

const RELATION_LABEL: Record<string, string> = {
  ownership: "지분 관계",
  sector: "같은 섹터",
  parent: "모기업",
  child: "자회사",
  supplier: "공급망",
  competitor: "경쟁사",
};

// 관계 타입별 시각 언어. parent/child는 진한 실선(지배구조), sector는 얇은 실선, competitor는 점선.
const RELATION_STROKE: Record<string, { opacity: number; dash: string; width: number }> = {
  parent: { opacity: 0.7, dash: "0", width: 1.5 },
  child: { opacity: 0.7, dash: "0", width: 1.5 },
  sector: { opacity: 0.18, dash: "0", width: 1 },
  supplier: { opacity: 0.5, dash: "0", width: 1.2 },
  competitor: { opacity: 0.5, dash: "3 3", width: 1.2 },
};

type SimNode = {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  fixed?: boolean;
};

export function RelatedCompanies({ ticker }: { ticker: string }) {
  const [data, setData] = useState<Response | null>(null);
  const [err, setErr] = useState(false);
  const [nodes, setNodes] = useState<SimNode[]>([]);
  const rafRef = useRef<number | null>(null);
  const hoverRef = useRef<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    fetch(`${API}/api/companies/${ticker}/related?limit=6`, { signal: ctl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d: Response) => {
        setData(d);
        // initial layout — 중심 고정, 피어는 원형 배치에서 시작
        const n = d.peers.length;
        const W = 360;
        const H = 220;
        const cx = W / 2;
        const cy = H / 2;
        const r = 80;
        const init: SimNode[] = [
          { id: d.center.ticker, x: cx, y: cy, vx: 0, vy: 0, fixed: true },
          ...d.peers.map((p, i) => {
            const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
            return {
              id: p.ticker,
              x: cx + Math.cos(angle) * r,
              y: cy + Math.sin(angle) * r,
              vx: 0,
              vy: 0,
            };
          }),
        ];
        setNodes(init);
      })
      .catch(() => setErr(true));
    return () => ctl.abort();
  }, [ticker]);

  // 물리 시뮬레이션 — spring(연결) + repulsion(전체) + center 고정.
  useEffect(() => {
    if (nodes.length === 0 || !data) return;
    const W = 360;
    const H = 220;
    const cx = W / 2;
    const cy = H / 2;
    const springLength = 78;
    const springK = 0.04;
    const repulsion = 900;
    const damping = 0.82;

    function tick() {
      setNodes((prev) => {
        const arr = prev.map((n) => ({ ...n }));
        const centerIdx = 0;
        // spring: center ↔ 각 peer
        for (let i = 1; i < arr.length; i++) {
          const a = arr[centerIdx];
          const b = arr[i];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
          const force = (dist - springLength) * springK;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          b.vx -= fx;
          b.vy -= fy;
        }
        // repulsion: 모든 pair
        for (let i = 0; i < arr.length; i++) {
          for (let j = i + 1; j < arr.length; j++) {
            const a = arr[i];
            const b = arr[j];
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const dsq = Math.max(20, dx * dx + dy * dy);
            const dist = Math.sqrt(dsq);
            const f = repulsion / dsq;
            const fx = (dx / dist) * f;
            const fy = (dy / dist) * f;
            if (!a.fixed) {
              a.vx -= fx;
              a.vy -= fy;
            }
            if (!b.fixed) {
              b.vx += fx;
              b.vy += fy;
            }
          }
        }
        // 적용 + damping + bounds
        for (const n of arr) {
          if (n.fixed) {
            n.x = cx;
            n.y = cy;
            n.vx = 0;
            n.vy = 0;
            continue;
          }
          n.vx *= damping;
          n.vy *= damping;
          n.x += n.vx;
          n.y += n.vy;
          // bounds padding
          const pad = 18;
          n.x = Math.max(pad, Math.min(W - pad, n.x));
          n.y = Math.max(pad, Math.min(H - pad, n.y));
        }
        return arr;
      });
      rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);
    // 3초 후 정지 (CPU 낭비 방지)
    const stop = setTimeout(() => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }, 3000);
    return () => {
      clearTimeout(stop);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [data, nodes.length]);

  if (err || !data || data.peers.length === 0) return null;

  const byId = new Map(nodes.map((n) => [n.id, n]));
  const center = byId.get(data.center.ticker);

  return (
    <section className="mt-10 border-t border-border/50 pt-8">
      <div className="flex items-baseline justify-between mb-6">
        <h2 className="font-serif text-[22px] tracking-tight">관계 그래프</h2>
        <span className="mono text-[11px] text-fg-3 uppercase tracking-[0.15em]">
          {RELATION_LABEL[data.relation] ?? data.relation} · {data.peers.length}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[360px_1fr] gap-6 items-start">
        <svg
          viewBox="0 0 360 220"
          className="w-full max-w-[360px] text-fg-3"
          role="img"
          aria-label={`${data.center.name ?? data.center.ticker}와 연결된 ${data.peers.length}개 종목 관계망`}
        >
          {/* 화살표 마커 — 지분 방향(parent→child) 표시용 */}
          <defs>
            <marker
              id="arrow-own"
              viewBox="0 0 8 8"
              refX="7"
              refY="4"
              markerWidth="5"
              markerHeight="5"
              orient="auto-start-reverse"
            >
              <path d="M0 0 L8 4 L0 8 z" fill="currentColor" fillOpacity="0.6" />
            </marker>
          </defs>
          {/* edges */}
          {center &&
            data.peers.map((p) => {
              const n = byId.get(p.ticker);
              if (!n) return null;
              const rel = p.relation ?? data.relation;
              const style = RELATION_STROKE[rel] ?? RELATION_STROKE.sector;
              const isHot = hover === p.ticker;
              const isOwnership = rel === "parent" || rel === "child";
              // parent: 주주→회사 (들어오는 화살표, peer→center)
              // child: 회사→자회사 (나가는 화살표, center→peer)
              const x1 = rel === "parent" ? n.x : center.x;
              const y1 = rel === "parent" ? n.y : center.y;
              const x2 = rel === "parent" ? center.x : n.x;
              const y2 = rel === "parent" ? center.y : n.y;
              return (
                <line
                  key={`edge-${p.ticker}`}
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={isHot ? "var(--color-accent)" : "currentColor"}
                  strokeOpacity={isHot ? 0.9 : style.opacity}
                  strokeWidth={isHot ? style.width + 0.5 : style.width}
                  strokeDasharray={style.dash}
                  markerEnd={isOwnership ? "url(#arrow-own)" : undefined}
                />
              );
            })}
          {/* center node */}
          {center && (
            <g>
              <circle cx={center.x} cy={center.y} r="5" fill="var(--color-accent)" />
              <text
                x={center.x}
                y={center.y + 18}
                textAnchor="middle"
                className="fill-[var(--color-fg)]"
                style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}
              >
                {data.center.ticker}
              </text>
            </g>
          )}
          {/* peer nodes */}
          {data.peers.map((p) => {
            const n = byId.get(p.ticker);
            if (!n) return null;
            const isHot = hover === p.ticker;
            return (
              <g
                key={p.ticker}
                onMouseEnter={() => {
                  hoverRef.current = p.ticker;
                  setHover(p.ticker);
                }}
                onMouseLeave={() => {
                  if (hoverRef.current === p.ticker) {
                    hoverRef.current = null;
                    setHover(null);
                  }
                }}
                style={{ cursor: "pointer" }}
              >
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={isHot ? 4 : 3}
                  fill={isHot ? "var(--color-accent)" : "currentColor"}
                />
                <text
                  x={n.x}
                  y={n.y + 14}
                  textAnchor="middle"
                  className="fill-[var(--color-fg-2)]"
                  style={{ fontFamily: "var(--font-mono)", fontSize: 9 }}
                >
                  {p.ticker}
                </text>
              </g>
            );
          })}
        </svg>

        <ul className="divide-y divide-border/40">
          {data.peers.map((p) => {
            const up = (p.change ?? 0) >= 0;
            const isHot = hover === p.ticker;
            const rel = p.relation ?? data.relation;
            const relTag = rel === "parent" ? "모기업" : rel === "child" ? "자회사" : "섹터";
            const relColor =
              rel === "parent" || rel === "child"
                ? "text-accent border-accent/40"
                : "text-fg-3 border-border";
            return (
              <li
                key={p.ticker}
                onMouseEnter={() => setHover(p.ticker)}
                onMouseLeave={() => setHover(null)}
              >
                <Link
                  href={`/c/${p.ticker}`}
                  className={`flex items-baseline justify-between gap-4 py-2.5 px-2 -mx-2 transition-colors ${
                    isHot ? "bg-bg-3" : "hover:bg-bg-2/50"
                  }`}
                >
                  <div className="min-w-0 flex-1 flex items-baseline gap-2">
                    <span
                      className={`mono text-[10px] border px-1.5 py-0.5 shrink-0 ${relColor}`}
                      title={`관계: ${relTag}`}
                    >
                      {relTag}
                    </span>
                    <div className="min-w-0">
                      <p className="text-[14px] text-fg truncate">
                        {p.name ?? p.ticker}
                      </p>
                      <p className="mono text-[11px] text-fg-3 mt-0.5">
                        {p.ticker}
                        {p.sector ? ` · ${p.sector}` : ""}
                        {p.stake_pct != null ? ` · ${p.stake_pct.toFixed(2)}%` : ""}
                      </p>
                    </div>
                  </div>
                  {p.change !== null && (
                    <span className={`mono text-[12px] tabular-nums ${up ? "price-up" : "price-down"}`}>
                      {up ? "+" : ""}
                      {p.change.toFixed(2)}%
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>

      <p className="mono text-[11px] text-fg-3 mt-4 leading-[1.65]">
        모기업·자회사는 CorporateOwnership edge(실선, 화살표). 섹터 피어는 얇은 선. hover 시 연결 하이라이트.
      </p>
    </section>
  );
}
