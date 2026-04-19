"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

const TOKEN_KEY = "comad_stock_token";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextRaw = searchParams.get("next");
  // 안전한 next: 내부 경로만 허용 (open redirect 방어)
  const next = nextRaw && nextRaw.startsWith("/") && !nextRaw.startsWith("//")
    ? nextRaw
    : "/watchlist";
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
    const body =
      mode === "register"
        ? { email, password, name }
        : { email, password };
    try {
      const r = await fetch(`${api}/api/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      localStorage.setItem(TOKEN_KEY, data.token);
      router.push(next);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "실패");
    }
  }

  return (
    <main className="mx-auto max-w-[420px] px-6 sm:px-8 py-20 sm:py-28">
      <p className="mono text-[11px] text-fg-3 uppercase tracking-[0.18em]">
        The Gongsi · 더공시
      </p>
      <h1 className="mt-3 font-serif text-[32px] leading-none tracking-[-0.01em]">
        {mode === "login" ? "로그인" : "가입"}
      </h1>
      <p className="mt-3 text-[13px] text-fg-2 leading-[1.65]">
        {mode === "login"
          ? "자연어 질의, 워치리스트, DD 메모 생성에 로그인이 필요합니다."
          : "이메일·비밀번호만으로 가입. 추적·광고·3rd-party 분석 없음."}
      </p>

      <form onSubmit={submit} className="mt-8 sm:mt-10 space-y-4">
        {mode === "register" && (
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="이름"
            autoComplete="name"
            required
            className="w-full bg-bg-2 border border-border px-4 py-3 text-[14px] focus:border-accent focus:outline-none"
          />
        )}
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="이메일"
          type="email"
          autoComplete="email"
          required
          className="w-full bg-bg-2 border border-border px-4 py-3 text-[14px] focus:border-accent focus:outline-none"
        />
        <div>
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="비밀번호 (8자 이상)"
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            minLength={8}
            aria-describedby="password-hint"
            className="w-full bg-bg-2 border border-border px-4 py-3 text-[14px] focus:border-accent focus:outline-none"
          />
          {mode === "register" && password.length > 0 && password.length < 8 && (
            <p id="password-hint" className="mt-1 text-[11px] text-sev-med">
              비밀번호는 8자 이상이어야 합니다 ({password.length}/8)
            </p>
          )}
        </div>

        <button
          type="submit"
          className="w-full mono text-[13px] text-accent border border-accent py-3 hover:bg-accent-dim transition-colors"
        >
          {mode === "login" ? "login →" : "register →"}
        </button>

        {err && <p className="text-[13px] text-sev-high">⚠ {err}</p>}
      </form>

      <button
        onClick={() => setMode(mode === "login" ? "register" : "login")}
        className="mt-8 mono text-[12px] text-fg-3 hover:text-fg-2"
      >
        {mode === "login" ? "계정이 없으신가요? 가입 →" : "이미 계정이 있나요? 로그인 →"}
      </button>

      <dl className="mt-12 border-t border-border/50 pt-6 space-y-3">
        {[
          ["DART 전수 수집", "공시 · 요약 · 심각도 플래그"],
          ["GraphRAG", "공급망 · 경쟁사 · 인사이더 연결"],
          ["BYOK", "본인 API 키로 AI 실행"],
        ].map(([k, v]) => (
          <div key={k} className="flex items-baseline gap-4 text-[12px]">
            <dt className="mono text-fg-3 uppercase tracking-[0.15em] w-[110px] shrink-0">
              {k}
            </dt>
            <dd className="text-fg-2">{v}</dd>
          </div>
        ))}
      </dl>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-[420px] px-8 py-32 text-fg-3">Loading…</main>}>
      <LoginForm />
    </Suspense>
  );
}
