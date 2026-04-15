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
    <main className="mx-auto max-w-[420px] px-8 py-32">
      <h1 className="font-serif text-[32px] leading-none">{mode === "login" ? "로그인" : "가입"}</h1>

      <form onSubmit={submit} className="mt-10 space-y-4">
        {mode === "register" && (
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="이름"
            required
            className="w-full bg-bg-2 border border-border px-4 py-3 text-[14px] focus:border-accent focus:outline-none"
          />
        )}
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="이메일"
          type="email"
          required
          className="w-full bg-bg-2 border border-border px-4 py-3 text-[14px] focus:border-accent focus:outline-none"
        />
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="비밀번호"
          type="password"
          required
          minLength={8}
          className="w-full bg-bg-2 border border-border px-4 py-3 text-[14px] focus:border-accent focus:outline-none"
        />

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
