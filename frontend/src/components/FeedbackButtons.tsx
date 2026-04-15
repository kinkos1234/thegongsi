"use client";

import { useState } from "react";

type Target =
  | { kind: "disclosure"; rcept_no: string }
  | { kind: "memo"; memo_version_id: string };

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

export function FeedbackButtons({ target }: { target: Target }) {
  const [state, setState] = useState<"idle" | "sending" | "ok" | "err">("idle");
  const [selected, setSelected] = useState<1 | -1 | null>(null);

  async function send(rating: 1 | -1) {
    if (state === "sending" || state === "ok") return;
    setSelected(rating);
    setState("sending");
    const path = target.kind === "disclosure" ? "disclosure" : "memo";
    const body =
      target.kind === "disclosure"
        ? { rcept_no: target.rcept_no, rating }
        : { memo_version_id: target.memo_version_id, rating };
    try {
      const r = await fetch(`${API}/api/feedback/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setState(r.ok ? "ok" : "err");
    } catch {
      setState("err");
    }
  }

  // 2초 뒤 err 상태 리셋
  if (state === "err") {
    setTimeout(() => {
      setState("idle");
      setSelected(null);
    }, 2500);
  }

  return (
    <div className="flex items-center gap-2 text-[13px] text-fg-3 select-none">
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          send(1);
        }}
        disabled={state === "sending" || state === "ok"}
        className={`px-2 py-1 leading-none border border-transparent hover:border-accent/60 hover:text-accent transition-colors disabled:cursor-not-allowed ${
          selected === 1 ? "text-accent border-accent/60" : ""
        }`}
        aria-label="유용함"
        title="유용함"
      >
        ▲
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          send(-1);
        }}
        disabled={state === "sending" || state === "ok"}
        className={`px-2 py-1 leading-none border border-transparent hover:border-sev-high/60 hover:text-sev-high transition-colors disabled:cursor-not-allowed ${
          selected === -1 ? "text-sev-high border-sev-high/60" : ""
        }`}
        aria-label="부정확"
        title="부정확"
      >
        ▼
      </button>
      {state === "sending" && <span className="mono text-[11px]">보내는 중…</span>}
      {state === "ok" && <span className="mono text-[11px] text-accent">감사합니다</span>}
      {state === "err" && <span className="mono text-[11px] text-sev-high">실패, 재시도</span>}
    </div>
  );
}
