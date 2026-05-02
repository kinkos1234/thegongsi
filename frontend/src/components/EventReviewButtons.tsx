"use client";

import { useState } from "react";
import { Check, Flag, MinusCircle, StickyNote } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";
const TOKEN_KEY = "comad_stock_token";

type ReviewStatus = "new" | "reviewed" | "dismissed" | "escalated";

export function EventReviewButtons({
  rceptNo,
  initialStatus,
  initialNote,
}: {
  rceptNo: string;
  initialStatus: ReviewStatus;
  initialNote?: string | null;
}) {
  const [status, setStatus] = useState<ReviewStatus>(initialStatus);
  const [note, setNote] = useState(initialNote ?? "");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState(false);
  const [noteOpen, setNoteOpen] = useState(Boolean(initialNote));

  async function send(next: Exclude<ReviewStatus, "new">) {
    const token = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
    if (!token) {
      setErr(true);
      return;
    }
    setBusy(next);
    setErr(false);
    try {
      const r = await fetch(`${API}/api/events/reviews`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ rcept_no: rceptNo, status: next, note: note.trim() || null }),
      });
      if (!r.ok) throw new Error("request failed");
      setStatus(next);
    } catch {
      setErr(true);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col items-start gap-2 sm:items-end">
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusPill status={status} />
        <button
          type="button"
          onClick={() => setNoteOpen((v) => !v)}
          className={`inline-flex h-7 w-7 items-center justify-center border transition-colors ${
            noteOpen || note.trim()
              ? "border-accent/60 text-accent"
              : "border-border/50 text-fg-3 hover:border-accent/60 hover:text-accent"
          }`}
          title="메모"
          aria-label="메모"
        >
          <StickyNote size={13} strokeWidth={1.8} />
        </button>
        {(["reviewed", "dismissed", "escalated"] as const).map((next) => {
          const Icon = next === "reviewed" ? Check : next === "dismissed" ? MinusCircle : Flag;
          const label = next === "reviewed" ? "검토" : next === "dismissed" ? "제외" : "주의";
          return (
          <button
            key={next}
            type="button"
            onClick={() => send(next)}
            disabled={busy !== null || status === next}
            className={`mono inline-flex h-7 items-center gap-1 border px-2 text-[10px] transition-colors disabled:cursor-not-allowed ${
              status === next
                ? "border-accent/60 text-accent"
                : "border-border/50 text-fg-3 hover:border-accent/60 hover:text-accent"
            }`}
            title={label}
          >
            <Icon size={12} strokeWidth={1.8} />
            <span>{busy === next ? "저장" : label}</span>
          </button>
          );
        })}
      </div>
      {noteOpen && (
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="메모"
          rows={2}
          className="w-full min-w-[220px] resize-none bg-bg-2 border border-border/50 px-2 py-1 text-[11px] text-fg-2 placeholder:text-fg-3 focus:border-accent focus:outline-none sm:w-[260px]"
        />
      )}
      {err && (
        <p className="mono text-[10px] text-sev-high">로그인 필요 또는 저장 실패</p>
      )}
    </div>
  );
}

function StatusPill({ status }: { status: ReviewStatus }) {
  const label =
    status === "reviewed" ? "검토됨" : status === "dismissed" ? "제외" : status === "escalated" ? "주의" : "신규";
  const tone =
    status === "escalated"
      ? "border-sev-high/50 text-sev-high"
      : status === "reviewed"
      ? "border-accent/50 text-accent"
      : status === "dismissed"
      ? "border-border/50 text-fg-3"
      : "border-border/50 text-fg-2";
  return <span className={`mono inline-flex h-7 items-center border px-2 text-[10px] ${tone}`}>{label}</span>;
}
