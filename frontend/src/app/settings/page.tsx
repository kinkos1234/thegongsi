"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const TOKEN_KEY = "comad_stock_token";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

type Usage = { date: string; memo: { used: number; limit: number }; ask: { used: number; limit: number } };
type Status = {
  configured_server_side: boolean;
  anthropic: boolean;
  openai: boolean;
  anthropic_hint: string | null;
  openai_hint: string | null;
  is_admin: boolean;
  server_fallback_usage: Usage;
};

export default function SettingsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [anthropic, setAnthropic] = useState("");
  const [openai, setOpenai] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const t = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
    setToken(t);
    if (t) loadStatus(t);
  }, []);

  async function loadStatus(t: string) {
    try {
      const r = await fetch(`${API}/api/byok/status`, { headers: { Authorization: `Bearer ${t}` } });
      if (r.ok) setStatus(await r.json());
    } catch {}
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setSaving(true);
    setErr(null);
    setMsg(null);
    try {
      // Anthropic 키 유효성 검증 먼저
      if (anthropic.trim()) {
        const v = await fetch(`${API}/api/byok/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ anthropic_key: anthropic.trim() }),
        });
        if (!v.ok) {
          const d = await v.json().catch(() => ({}));
          throw new Error(d.detail || "Anthropic 키 검증 실패");
        }
      }

      const body: Record<string, string | null> = {};
      if (anthropic.trim()) body.anthropic_key = anthropic.trim();
      if (openai.trim()) body.openai_key = openai.trim();
      const r = await fetch(`${API}/api/byok/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      setMsg("저장됨. 이제 AI 호출은 내 키로 실행됩니다.");
      setAnthropic("");
      setOpenai("");
      loadStatus(token);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setSaving(false);
    }
  }

  async function clearKeys() {
    if (!token) return;
    if (!confirm("등록된 모든 API 키를 삭제합니다. 계속?")) return;
    const r = await fetch(`${API}/api/byok/`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (r.ok) {
      setMsg("키 삭제됨");
      loadStatus(token);
    }
  }

  if (!token) {
    return (
      <main className="mx-auto max-w-[720px] px-8 py-20">
        <h1 className="font-serif text-[32px]">로그인이 필요합니다.</h1>
        <Link href="/login?next=/settings" className="mt-6 inline-block mono text-accent border-b border-accent">
          login →
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-[720px] px-8 py-20">
      <p className="mono text-[12px] text-fg-3 uppercase tracking-wider">SETTINGS · BYOK</p>
      <h1 className="mt-3 font-serif text-[40px] leading-[1.1] tracking-[-0.01em]">내 API 키</h1>
      <p className="mt-4 text-[15px] text-fg-2 leading-[1.7]">
        본인의 Anthropic Claude 키를 등록하면 DD 메모·자연어 질의 시 <em>내 키</em>로 과금됩니다.
        서버 관리자 키는 fallback이며 일일 한도 적용. 키는 Fernet 암호화 저장.
      </p>

      {status?.is_admin && (
        <div className="mt-6 border border-accent/50 bg-accent-dim/20 px-4 py-3 text-[13px]">
          <span className="mono text-[11px] text-accent uppercase tracking-wider">ADMIN</span>{" "}
          <span className="text-fg-2">운영자 계정 — 서버 키 쿼터 면제</span>
        </div>
      )}

      {status && (
        <section className="mt-10 border-t border-border/50 pt-6 text-[14px] space-y-1">
          <h2 className="mono text-[11px] uppercase tracking-wider text-fg-3 mb-3">현재 상태</h2>
          <p>
            서버측 암호화 키:{" "}
            <span className={status.configured_server_side ? "text-accent" : "text-sev-high"}>
              {status.configured_server_side ? "구성됨" : "미구성 — FIELD_ENCRYPTION_KEY 필요"}
            </span>
          </p>
          <p>
            내 Anthropic 키:{" "}
            {status.anthropic ? (
              <span className="text-accent">
                등록됨 <span className="mono text-fg-3 ml-2">{status.anthropic_hint}</span>
              </span>
            ) : (
              <span className="text-fg-3">미등록 (서버 키 fallback)</span>
            )}
          </p>
          <p>
            내 OpenAI 키:{" "}
            {status.openai ? (
              <span className="text-accent">
                등록됨 <span className="mono text-fg-3 ml-2">{status.openai_hint}</span>
              </span>
            ) : (
              <span className="text-fg-3">미등록</span>
            )}
          </p>

          {!status.is_admin && !status.anthropic && (
            <div className="mt-4 pt-3 border-t border-border/30 text-[12px] text-fg-3">
              <p className="mono uppercase tracking-wider mb-1">오늘 서버 키 사용</p>
              <p>
                메모 {status.server_fallback_usage.memo.used}/{status.server_fallback_usage.memo.limit || "∞"} ·{" "}
                ask {status.server_fallback_usage.ask.used}/{status.server_fallback_usage.ask.limit || "∞"}
              </p>
            </div>
          )}
        </section>
      )}

      <form onSubmit={save} className="mt-12 space-y-6">
        <div>
          <label className="mono text-[12px] text-fg-3 uppercase tracking-wider block mb-2">
            Anthropic Claude API key
          </label>
          <input
            type="password"
            value={anthropic}
            onChange={(e) => setAnthropic(e.target.value)}
            placeholder="sk-ant-api03-…"
            className="w-full bg-bg-2 border border-border px-4 py-3 mono text-[13px] focus:border-accent focus:outline-none"
          />
          <p className="mt-1 text-[11px] text-fg-3">
            발급:{" "}
            <a
              href="https://console.anthropic.com/settings/keys"
              target="_blank"
              rel="noreferrer"
              className="border-b border-fg-3 hover:text-accent hover:border-accent"
            >
              console.anthropic.com/settings/keys
            </a>{" "}
            · 저장 전 1-토큰 테스트로 유효성 검증
          </p>
        </div>

        <div>
          <label className="mono text-[12px] text-fg-3 uppercase tracking-wider block mb-2">
            OpenAI API key (선택)
          </label>
          <input
            type="password"
            value={openai}
            onChange={(e) => setOpenai(e.target.value)}
            placeholder="sk-proj-…"
            className="w-full bg-bg-2 border border-border px-4 py-3 mono text-[13px] focus:border-accent focus:outline-none"
          />
        </div>

        <div className="flex gap-4">
          <button
            type="submit"
            disabled={saving || !(anthropic || openai)}
            className="mono text-[13px] text-accent border border-accent px-5 py-2 hover:bg-accent-dim transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {saving ? "검증·저장 중…" : "저장"}
          </button>
          {status && (status.anthropic || status.openai) && (
            <button
              type="button"
              onClick={clearKeys}
              className="mono text-[12px] text-fg-3 hover:text-sev-high"
            >
              모든 키 삭제
            </button>
          )}
        </div>

        {msg && <p className="text-[13px] text-accent">{msg}</p>}
        {err && <p className="text-[13px] text-sev-high">⚠ {err}</p>}
      </form>
    </main>
  );
}
