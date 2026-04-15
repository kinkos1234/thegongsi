"use client";

import { useState } from "react";

type Answer = {
  question: string;
  cypher: string;
  rows: Record<string, unknown>[];
  answer: string | null;
};

export default function AskPage() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [ans, setAns] = useState<Answer | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setLoading(true);
    setErr(null);
    try {
      const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
      const r = await fetch(`${api}/api/qa/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!r.ok) throw new Error(await r.text());
      setAns(await r.json());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "실행 실패");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-[820px] px-8 py-20">
      <h1 className="font-serif text-[40px] leading-none tracking-[-0.01em]">GraphRAG Q&amp;A</h1>
      <p className="mt-4 text-[15px] text-fg-2">
        자연어로 물어보면 Cypher로 변환해 기업 관계 그래프에서 답을 찾습니다.
      </p>

      <form onSubmit={submit} className="mt-12">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="HBM 공급망에서 최근 이상 공시가 있는 회사?"
          className="w-full bg-bg-2 border border-border px-5 py-4 text-[15px] focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading}
          className="mt-3 mono text-[13px] text-accent border-b border-accent disabled:opacity-40"
        >
          {loading ? "실행 중…" : "ask →"}
        </button>
      </form>

      {loading && (
        <div className="mt-12 space-y-3">
          <div className="h-[24px] bg-bg-2 animate-pulse w-3/4" />
          <div className="h-[24px] bg-bg-2 animate-pulse w-2/3" />
          <div className="h-[24px] bg-bg-2 animate-pulse w-1/2" />
        </div>
      )}

      {err && <p className="mt-8 text-[14px] text-sev-high">⚠ {err}</p>}

      {ans && (
        <section className="mt-16">
          {ans.answer && (
            <div className="mb-10 border-l-2 border-accent pl-6 py-2">
              <p className="font-serif text-[18px] leading-[1.7] text-fg whitespace-pre-wrap">{ans.answer}</p>
            </div>
          )}
          <details className="mb-6 text-[13px] text-fg-3">
            <summary className="cursor-pointer mono">근거 · cypher</summary>
            <pre className="mono mt-2 bg-bg-2 p-4 text-[12px] whitespace-pre-wrap">{ans.cypher}</pre>
            <h3 className="mono text-[11px] text-fg-3 uppercase mt-4 mb-2">rows</h3>
            {ans.rows.length === 0 ? (
              <p className="text-fg-3">결과 없음</p>
            ) : (
              <pre className="mono bg-bg-2 border border-border/50 p-4 overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(ans.rows, null, 2)}
              </pre>
            )}
          </details>
        </section>
      )}
    </main>
  );
}
