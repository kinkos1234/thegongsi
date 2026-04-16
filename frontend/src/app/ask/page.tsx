"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Markdown } from "@/components/Markdown";

type ToolCall = { name: string; args: Record<string, unknown>; result_summary: Record<string, unknown> };
type Answer = {
  question: string;
  tools_used: ToolCall[];
  answer: string | null;
};

const TOKEN_KEY = "comad_stock_token";

export default function AskPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [ans, setAns] = useState<Answer | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const t = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
    if (!t) {
      router.replace("/login?next=/ask");
      return;
    }
    setToken(t);
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim() || !token || loading) return;  // 중복 submit 방어
    setLoading(true);
    setErr(null);
    try {
      const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
      const r = await fetch(`${api}/api/qa/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ question: q }),
      });
      if (r.status === 401) {
        router.replace("/login?next=/ask");
        return;
      }
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        // 쿼터 초과 / 검증된 에러만 노출. 500 등은 generic 메시지
        const detail = typeof d.detail === "string" ? d.detail : "";
        if (r.status === 429 || r.status === 400) {
          throw new Error(detail || "요청을 처리할 수 없습니다");
        }
        throw new Error("일시적인 오류가 발생했어요. 잠시 후 다시 시도해주세요.");
      }
      setAns(await r.json());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "실행 실패");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return <main className="mx-auto max-w-[820px] px-8 py-20 text-fg-3">로그인 확인 중…</main>;
  }

  return (
    <main className="mx-auto max-w-[820px] px-8 py-20">
      <p className="mono text-[12px] text-fg-3 uppercase tracking-wider">ASK</p>
      <h1 className="mt-3 font-serif text-[40px] leading-[1.1] tracking-[-0.01em]">
        자연어 질의
      </h1>
      <p className="mt-4 text-[15px] text-fg-2">
        기업 관계 그래프와 DART 공시에서 답을 찾습니다.
      </p>

      <form onSubmit={submit} className="mt-12">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="HBM 공급망에서 최근 이상 공시가 있는 회사?"
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              (e.currentTarget.form as HTMLFormElement)?.requestSubmit();
            }
          }}
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
              <Markdown content={ans.answer} tone="serif" />
            </div>
          )}
          {ans.tools_used && ans.tools_used.length > 0 && (
            <details className="mb-6 text-[13px] text-fg-3">
              <summary className="cursor-pointer mono">
                근거 · {ans.tools_used.length}건 도구 호출
              </summary>
              <ul className="mt-3 space-y-2">
                {ans.tools_used.map((t, i) => (
                  <li key={i} className="bg-bg-2 p-3 border border-border/30">
                    <p className="mono text-[12px] text-accent">{t.name}</p>
                    <pre className="mono mt-1 text-[11px] whitespace-pre-wrap text-fg-3">
                      args: {JSON.stringify(t.args, null, 2)}
                    </pre>
                    <pre className="mono mt-1 text-[11px] whitespace-pre-wrap text-fg-2">
                      result: {JSON.stringify(t.result_summary)}
                    </pre>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}
    </main>
  );
}
