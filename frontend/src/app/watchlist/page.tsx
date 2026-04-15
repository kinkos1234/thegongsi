"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Item = { ticker: string; added_at: string };

const TOKEN_KEY = "comad_stock_token";

export default function WatchlistPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [ticker, setTicker] = useState("");
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    setToken(typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null);
  }, []);

  useEffect(() => {
    if (!token) return;
    load(token);
  }, [token]);

  async function load(t: string) {
    const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
    const r = await fetch(`${api}/api/watchlist/`, { headers: { Authorization: `Bearer ${t}` } });
    if (r.ok) setItems(await r.json());
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!ticker.trim() || !token) return;
    const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
    await fetch(`${api}/api/watchlist/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ ticker: ticker.trim() }),
    });
    setTicker("");
    load(token);
  }

  async function remove(t: string) {
    if (!token) return;
    const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
    await fetch(`${api}/api/watchlist/${t}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    load(token);
  }

  if (!token) {
    return (
      <main className="mx-auto max-w-[720px] px-8 py-20">
        <h1 className="font-serif text-[32px]">로그인이 필요합니다.</h1>
        <Link href="/login" className="mt-6 inline-block mono text-accent border-b border-accent">
          login →
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-[720px] px-8 py-20">
      <h1 className="font-serif text-[40px] leading-none tracking-[-0.01em]">관심 종목</h1>

      <form onSubmit={add} className="mt-10 flex gap-3">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="6자리 종목코드 (예: 005930)"
          className="flex-1 bg-bg-2 border border-border px-4 py-3 mono text-[14px] focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          className="mono text-[13px] text-accent border border-accent px-4 hover:bg-accent-dim transition-colors"
        >
          add
        </button>
      </form>

      <ul className="mt-12 border-t border-border/50">
        {items.length === 0 && <li className="py-8 text-fg-3">아직 관심 종목이 없습니다.</li>}
        {items.map((i) => (
          <li key={i.ticker} className="flex items-center justify-between border-b border-border/50 py-4">
            <Link href={`/c/${i.ticker}`} className="mono text-[14px] hover:text-accent">
              {i.ticker}
            </Link>
            <button
              onClick={() => remove(i.ticker)}
              className="mono text-[12px] text-fg-3 hover:text-sev-high"
            >
              remove
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
