"use client";

import { useState } from "react";

type Target =
  | { kind: "disclosure"; rcept_no: string }
  | { kind: "memo"; memo_version_id: string };

export function FeedbackButtons({ target }: { target: Target }) {
  const [sent, setSent] = useState<1 | -1 | null>(null);

  async function send(rating: 1 | -1) {
    if (sent) return;
    setSent(rating);
    const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
    const path = target.kind === "disclosure" ? "disclosure" : "memo";
    const body = target.kind === "disclosure"
      ? { rcept_no: target.rcept_no, rating }
      : { memo_version_id: target.memo_version_id, rating };
    try {
      await fetch(`${api}/api/feedback/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch {
      // 익명 피드백 — 실패해도 사용자 방해 안 함
    }
  }

  return (
    <div className="flex items-center gap-3 text-[11px] text-fg-3">
      <button
        onClick={() => send(1)}
        disabled={sent !== null}
        className={`hover:text-accent transition-colors ${sent === 1 ? "text-accent" : ""}`}
        aria-label="유용함"
      >
        ▲
      </button>
      <button
        onClick={() => send(-1)}
        disabled={sent !== null}
        className={`hover:text-sev-high transition-colors ${sent === -1 ? "text-sev-high" : ""}`}
        aria-label="부정확"
      >
        ▼
      </button>
      {sent && <span className="mono">thanks</span>}
    </div>
  );
}
