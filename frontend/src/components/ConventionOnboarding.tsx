"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const ASKED_KEY = "comad_stock_convention_asked";
const CONV_KEY = "comad_stock_convention";
type Convention = "us" | "kr";

/** 첫 방문 시 한 번만 노출되는 컨벤션 선택 배너.
 *
 * 한국 증권 UX 관습(빨강=상승)과 글로벌 관습(초록=상승) 중
 * 본인 선호를 명시적으로 물어본다. 선택 즉시 저장, ESC·닫기로 dismiss.
 * 첫 버튼에 자동 포커스, 페이지 본문 포커스 가능 요소는 tabindex 방해 안 하도록
 * inert 대신 단순 focus 반환 정책 사용.
 */
export function ConventionOnboarding() {
  const [show, setShow] = useState(false);
  const firstBtnRef = useRef<HTMLButtonElement | null>(null);
  const lastFocusRef = useRef<Element | null>(null);

  useEffect(() => {
    const asked = localStorage.getItem(ASKED_KEY);
    if (!asked) setShow(true);
  }, []);

  const close = useCallback(() => {
    localStorage.setItem(ASKED_KEY, "1");
    setShow(false);
    // 이전 포커스 복구
    if (lastFocusRef.current instanceof HTMLElement) {
      lastFocusRef.current.focus();
    }
  }, []);

  function pick(conv: Convention) {
    localStorage.setItem(CONV_KEY, conv);
    document.documentElement.setAttribute("data-convention", conv);
    close();
  }

  // ESC 처리 + 자동 포커스
  useEffect(() => {
    if (!show) return;
    lastFocusRef.current = document.activeElement;
    // 약간 지연 후 포커스(렌더 완료 보장)
    const t = setTimeout(() => firstBtnRef.current?.focus(), 50);
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(t);
      document.removeEventListener("keydown", onKey);
    };
  }, [show, close]);

  if (!show) return null;

  return (
    <aside
      role="dialog"
      aria-label="가격 색상 관습 선택"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-accent/40 bg-bg-2/95 backdrop-blur supports-[backdrop-filter]:bg-bg-2/70"
    >
      <div className="mx-auto max-w-[1080px] px-6 sm:px-8 py-4 flex flex-wrap items-center gap-x-6 gap-y-3 justify-between">
        <div className="min-w-0">
          <p className="mono text-[11px] text-accent uppercase tracking-[0.15em]">
            가격 색상 관습
          </p>
          <p className="mt-1 text-[13px] text-fg-2">
            한국은 <span className="text-sev-high">상승 = 빨강</span>, 미국·글로벌은{" "}
            <span className="text-accent">상승 = 초록</span>. 어느 쪽을 쓰시겠어요?
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            ref={firstBtnRef}
            onClick={() => pick("kr")}
            className="mono text-[12px] px-3 py-1.5 border border-sev-high text-sev-high hover:bg-sev-high/10 transition-colors"
          >
            KR · 빨강 상승
          </button>
          <button
            onClick={() => pick("us")}
            className="mono text-[12px] px-3 py-1.5 border border-accent text-accent hover:bg-accent-dim transition-colors"
          >
            US · 초록 상승
          </button>
          <button
            onClick={close}
            aria-label="닫기 (ESC)"
            className="mono text-[12px] px-2 py-1.5 text-fg-3 hover:text-fg-2"
          >
            ×
          </button>
        </div>
      </div>
    </aside>
  );
}
