"use client";

import { useEffect, useState } from "react";
import { ExternalLink, X } from "lucide-react";

type Preview = {
  rcept_no: string;
  ticker: string;
  title: string;
  date: string;
  summary_ko: string | null;
  fields: Record<string, string>;
  dart_url: string;
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

export function DisclosurePreview({
  rceptNo,
  onClose,
}: {
  rceptNo: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<Preview | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/disclosures/${rceptNo}/preview`)
      .then((r) => (r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)))
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setErr(String(e)));
    return () => {
      cancelled = true;
    };
  }, [rceptNo]);

  // ESC 닫기
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const fieldEntries = data ? Object.entries(data.fields) : [];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="preview-title"
      className="fixed inset-0 z-50 bg-bg/80 backdrop-blur-sm flex items-start justify-center overflow-y-auto p-4 md:p-8"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[760px] bg-bg-2 border border-border/60 shadow-2xl"
      >
        <header className="flex items-start justify-between border-b border-border/50 px-6 py-4 gap-4">
          <div className="min-w-0">
            <p id="preview-title" className="font-serif text-[18px] leading-tight truncate">
              {data?.title ?? "로딩 중…"}
            </p>
            {data && (
              <p className="mono text-[11px] text-fg-3 mt-1">
                {data.date} · {data.ticker} · rcept_no={data.rcept_no}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="닫기"
            className="text-fg-3 hover:text-fg transition-colors p-1 -m-1"
          >
            <X size={18} strokeWidth={1.75} />
          </button>
        </header>

        <div className="px-6 py-5 max-h-[70vh] overflow-y-auto">
          {err && (
            <p className="text-[13px] text-sev-high mono">
              미리보기 불가: {err}. DART 원문으로 열어주세요.
            </p>
          )}
          {!err && !data && (
            <div className="space-y-2">
              <div className="h-4 w-1/3 bg-bg-3 animate-pulse" />
              <div className="h-4 w-2/3 bg-bg-3 animate-pulse" />
              <div className="h-4 w-1/2 bg-bg-3 animate-pulse" />
            </div>
          )}
          {data?.summary_ko && (
            <section className="mb-6">
              <h3 className="mono text-[11px] text-fg-3 uppercase tracking-wider mb-2">AI 요약</h3>
              <p className="text-[14px] text-fg leading-[1.7]">{data.summary_ko}</p>
            </section>
          )}
          {data && fieldEntries.length > 0 && (
            <section>
              <h3 className="mono text-[11px] text-fg-3 uppercase tracking-wider mb-3">핵심 필드</h3>
              <table className="w-full text-[13px]">
                <tbody>
                  {fieldEntries.map(([k, v]) => (
                    <tr key={k} className="border-b border-border/40">
                      <th
                        scope="row"
                        className="text-left py-2 pr-4 font-normal text-fg-2 align-top w-[45%] max-w-[280px]"
                      >
                        {k}
                      </th>
                      <td className="py-2 text-fg break-words">{v || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
          {data && fieldEntries.length === 0 && !data.summary_ko && !err && (
            <p className="text-[13px] text-fg-3">
              구조화된 필드를 찾을 수 없습니다. 원문에서 확인해주세요.
            </p>
          )}
        </div>

        {data && (
          <footer className="flex items-center justify-between border-t border-border/50 px-6 py-3 text-[12px]">
            <span className="mono text-fg-3">OpenDART document.xml 기반</span>
            <a
              href={data.dart_url}
              target="_blank"
              rel="noreferrer"
              className="mono text-accent hover:underline inline-flex items-center gap-1"
            >
              DART 원문
              <ExternalLink size={12} strokeWidth={1.75} />
            </a>
          </footer>
        )}
      </div>
    </div>
  );
}
