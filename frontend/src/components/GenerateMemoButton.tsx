"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

export function GenerateMemoButton({ ticker }: { ticker: string }) {
  const router = useRouter();
  const [state, setState] = useState<"idle" | "generating" | "done" | "error">("idle");
  const [err, setErr] = useState<string | null>(null);

  async function generate() {
    setState("generating");
    setErr(null);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("comad_stock_token") : null;
      const r = await fetch(`${API}/api/memos/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ ticker }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      setState("done");
      router.refresh();
    } catch (e) {
      setState("error");
      setErr(e instanceof Error ? e.message : "실패");
    }
  }

  return (
    <div>
      <button
        onClick={generate}
        disabled={state === "generating"}
        className="mono text-[12px] text-accent border border-accent px-4 py-2 hover:bg-accent-dim transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {state === "idle" && `generate memo for ${ticker} →`}
        {state === "generating" && "생성 중… (30~60초)"}
        {state === "done" && "✓ 완료 — regenerate →"}
        {state === "error" && "재시도 →"}
      </button>
      {err && <p className="mt-3 text-[12px] text-sev-high">⚠ {err}</p>}
    </div>
  );
}
