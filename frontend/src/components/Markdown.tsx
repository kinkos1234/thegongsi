"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ReactNode } from "react";

/**
 * DD 메모용 마크다운 렌더. 편집자적 톤 유지 — 링크는 accent, 테이블은 최소 보더.
 * [출처: rcept_no=xxx] 패턴은 자동으로 컴팩트 DART 링크로 변환.
 */
export function Markdown({ content, tone = "body" }: { content: string; tone?: "body" | "serif" }) {
  const isSerif = tone === "serif";
  return (
    <div className={isSerif ? "font-serif text-[18px] leading-[1.7]" : "text-[14px] leading-[1.65] text-fg-2"}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => (
            <p className={isSerif ? "mb-5 last:mb-0" : "mb-3 last:mb-0"}>
              {renderCitationsInChildren(children)}
            </p>
          ),
          strong: ({ children }) => <strong className="text-fg font-semibold">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => <ul className="list-disc ml-5 mb-3 space-y-1.5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal ml-5 mb-3 space-y-1.5">{children}</ol>,
          li: ({ children }) => <li>{renderCitationsInChildren(children)}</li>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-accent border-b border-accent/40 hover:border-accent"
            >
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="mono text-[12px] bg-bg-3 px-1.5 py-0.5 rounded text-fg-2">{children}</code>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-accent/40 pl-4 italic text-fg-2 my-3">{children}</blockquote>
          ),
          h1: ({ children }) => <h2 className="font-serif text-[22px] mt-5 mb-3">{children}</h2>,
          h2: ({ children }) => <h3 className="font-serif text-[18px] mt-4 mb-2">{children}</h3>,
          h3: ({ children }) => (
            <h4 className="mono text-[12px] uppercase tracking-wider text-fg-3 mt-4 mb-2">{children}</h4>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-4">
              <table className="w-full text-[13px] border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="border-b border-border">{children}</thead>,
          th: ({ children }) => <th className="text-left py-2 pr-4 mono text-[11px] uppercase tracking-wider text-fg-3">{children}</th>,
          td: ({ children }) => <td className="py-2 pr-4 border-b border-border/30">{children}</td>,
          hr: () => <hr className="border-border/40 my-4" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

/** 출처 각주를 컴팩트 DART 링크로 치환. children이 문자열이 아니면 그대로. */
function renderCitationsInChildren(children: ReactNode): ReactNode {
  if (typeof children === "string") {
    return transformCitations(children);
  }
  if (Array.isArray(children)) {
    return children.map((c, i) => <span key={i}>{renderCitationsInChildren(c)}</span>);
  }
  return children;
}

function transformCitations(text: string): ReactNode[] {
  const parts = text.split(/(\[(?:출처:\s*)?rcept_no=\d+(?:,\s*rcept_no=\d+)*\])/g);
  return parts.map((p, i) => {
    const matches = Array.from(p.matchAll(/rcept_no=(\d+)/g));
    if (matches.length > 0) {
      // inline flow — 각 링크는 nowrap이되, 링크들 사이에서는 줄바꿈 허용
      return (
        <span key={i}>
          {matches.map((m, j) => (
            <a
              key={j}
              href={`https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${m[1]}`}
              target="_blank"
              rel="noreferrer"
              className="mono text-[10px] text-fg-3 hover:text-accent whitespace-nowrap ml-0.5"
              title={`DART rcept_no=${m[1]}`}
            >
              [{m[1].slice(0, 8)}…]
            </a>
          ))}
        </span>
      );
    }
    return <span key={i}>{p}</span>;
  });
}
