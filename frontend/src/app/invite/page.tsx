"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { LoginGate } from "@/components/LoginGate";

const TOKEN_KEY = "comad_stock_token";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

function InviteContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const inviteToken = searchParams.get("token") ?? "";
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "accepting" | "accepted" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setAuthToken(typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null);
  }, []);

  async function accept() {
    if (!authToken || !inviteToken) return;
    setStatus("accepting");
    setMessage(null);
    try {
      const r = await fetch(`${API}/api/orgs/invitations/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
        body: JSON.stringify({ token: inviteToken }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      setStatus("accepted");
      setMessage(`조직 참여 완료 · role=${data.role}`);
      setTimeout(() => router.push("/settings"), 800);
    } catch (e) {
      setStatus("error");
      setMessage(e instanceof Error ? e.message : "초대 수락 실패");
    }
  }

  if (!authToken) {
    return (
      <LoginGate
        title="초대 수락은 로그인이 필요합니다."
        hint="초대받은 이메일과 같은 계정으로 로그인한 뒤 다시 수락해주세요."
        next={`/invite?token=${encodeURIComponent(inviteToken)}`}
      />
    );
  }

  return (
    <main className="mx-auto max-w-[520px] px-6 sm:px-8 py-20 sm:py-28">
      <p className="mono text-[11px] text-fg-3 uppercase tracking-[0.18em]">
        Organization invite
      </p>
      <h1 className="mt-3 font-serif text-[34px] leading-[1.08]">팀 초대 수락</h1>
      <p className="mt-4 text-[14px] leading-[1.7] text-fg-2">
        초대를 수락하면 이 계정의 기본 워크스페이스가 초대한 조직으로 전환됩니다.
      </p>

      <div className="mt-8 border border-border/60 bg-bg-2/60 p-4">
        <p className="mono text-[11px] text-fg-3 uppercase tracking-wider">invite token</p>
        <p className="mono mt-2 text-[12px] text-fg-2 break-all">{inviteToken || "-"}</p>
      </div>

      <button
        onClick={accept}
        disabled={!inviteToken || status === "accepting" || status === "accepted"}
        className="mt-8 mono text-[13px] text-accent border border-accent px-5 py-3 hover:bg-accent-dim transition-colors disabled:opacity-40"
      >
        {status === "accepting" ? "accepting…" : status === "accepted" ? "accepted" : "accept invite"}
      </button>

      {message && (
        <p className={`mt-4 text-[13px] ${status === "error" ? "text-sev-high" : "text-accent"}`}>
          {message}
        </p>
      )}
    </main>
  );
}

export default function InvitePage() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-[520px] px-8 py-32 text-fg-3">Loading…</main>}>
      <InviteContent />
    </Suspense>
  );
}
