"use client";

import { useEffect, useState } from "react";

type Target =
  | { kind: "disclosure"; rcept_no: string }
  | { kind: "memo"; memo_version_id: string };

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

function targetKey(target: Target): string {
  return target.kind === "disclosure"
    ? `tg_fb_d_${target.rcept_no}`
    : `tg_fb_m_${target.memo_version_id}`;
}

export function FeedbackButtons({ target }: { target: Target }) {
  const [state, setState] = useState<"idle" | "sending" | "ok" | "err">("idle");
  const [selected, setSelected] = useState<1 | -1 | null>(null);

  // 이미 이 사용자가 투표했는지 localStorage로 확인
  useEffect(() => {
    if (typeof window === "undefined") return;
    const prev = localStorage.getItem(targetKey(target));
    if (prev === "1" || prev === "-1") {
      setSelected(Number(prev) as 1 | -1);
      setState("ok");
    }
  }, [target]);

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
      if (r.ok) {
        setState("ok");
        localStorage.setItem(targetKey(target), String(rating));
      } else {
        setState("err");
      }
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
