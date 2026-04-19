import Link from "next/link";

/** 로그인 가드 페이지 공통 레이아웃 — 상단 여백 과다 방지 위해 화면 중앙 카드로 배치. */
export function LoginGate({
  title,
  hint,
  next,
}: {
  title: string;
  hint?: string;
  next: string;
}) {
  return (
    <main className="mx-auto max-w-[720px] px-6 sm:px-8 min-h-[calc(100vh-200px)] flex items-center">
      <div className="w-full border-l-2 border-accent/60 pl-6 py-4">
        <p className="mono text-[11px] text-fg-3 uppercase tracking-[0.18em]">
          LOGIN REQUIRED
        </p>
        <h1 className="mt-2 font-serif text-[28px] sm:text-[32px] leading-[1.15]">
          {title}
        </h1>
        {hint && (
          <p className="mt-3 text-[14px] text-fg-2 leading-[1.6]">{hint}</p>
        )}
        <Link
          href={`/login?next=${encodeURIComponent(next)}`}
          className="mt-6 inline-block mono text-[13px] text-accent border-b border-accent hover:bg-accent-dim px-1"
        >
          login →
        </Link>
      </div>
    </main>
  );
}
