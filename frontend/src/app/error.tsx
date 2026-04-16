"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="mx-auto max-w-[720px] px-8 py-24">
      <p className="mono text-[11px] tracking-widest text-fg-3 uppercase mb-3">
        Error
      </p>
      <h1 className="font-serif text-[34px] leading-[1.15] text-fg mb-4">
        페이지를 표시할 수 없습니다.
      </h1>
      <p className="text-[14px] text-fg-2 mb-8">
        일시적인 오류가 발생했어요. 새로고침하거나 잠시 후 다시 시도해주세요.
      </p>
      <div className="flex gap-4">
        <button
          onClick={() => reset()}
          className="mono text-[13px] text-accent border-b border-accent"
        >
          retry →
        </button>
        <a
          href="/"
          className="mono text-[13px] text-fg-2 border-b border-fg-2 hover:text-fg"
        >
          home →
        </a>
      </div>
    </main>
  );
}
