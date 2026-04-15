"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

type CompanySuggestion = {
  ticker: string;
  name: string;
  market: string;
  sector: string | null;
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

export function HomeSearch() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [items, setItems] = useState<CompanySuggestion[]>([]);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!q.trim()) {
      setItems([]);
      return;
    }
    const ctl = new AbortController();
    fetch(`${API}/api/companies/?q=${encodeURIComponent(q)}&limit=8`, { signal: ctl.signal })
      .then((r) => (r.ok ? r.json() : []))
      .then((rows) => {
        setItems(rows);
        setActive(0);
        setOpen(true);
      })
      .catch(() => {});
    return () => ctl.abort();
  }, [q]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  function go(ticker: string) {
    router.push(`/c/${ticker}`);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (!open || items.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(items.length - 1, a + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(items[active].ticker);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div ref={ref} className="relative mt-12">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => items.length > 0 && setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder="종목 검색 — 종목명·티커·섹터 (예: 삼성전자, 005930, 반도체)"
        className="w-full bg-bg-2 border border-border px-5 py-4 text-[15px] focus:border-accent focus:outline-none"
      />
      {open && items.length > 0 && (
        <ul className="absolute top-full left-0 right-0 mt-1 bg-bg-2 border border-border/80 max-h-[320px] overflow-y-auto z-30">
          {items.map((c, i) => (
            <li key={c.ticker}>
              <button
                onMouseEnter={() => setActive(i)}
                onClick={() => go(c.ticker)}
                className={`w-full text-left px-4 py-2 flex items-baseline gap-3 transition-colors ${
                  i === active ? "bg-bg-3" : ""
                }`}
              >
                <span className="font-serif text-[15px] text-fg">{c.name}</span>
                <span className="mono text-[12px] text-fg-3">
                  {c.ticker} · {c.market}
                </span>
                {c.sector && (
                  <span className="text-[11px] text-fg-3 ml-auto">{c.sector}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
