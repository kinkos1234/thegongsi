import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-[720px] px-8 py-32 text-center">
      <p className="mono text-[12px] text-fg-3 uppercase tracking-wider">404 · company not found</p>
      <h1 className="mt-6 font-serif text-[48px] leading-[1.1] tracking-[-0.01em]">
        해당 종목을 찾을 수 없습니다.
      </h1>
      <p className="mt-6 text-[15px] text-fg-2">
        6자리 KRX 종목코드를 확인해주세요 (예: 005930 — 삼성전자).
      </p>
      <Link href="/" className="mt-10 inline-block mono text-[13px] text-accent border-b border-accent">
        home →
      </Link>
    </main>
  );
}
