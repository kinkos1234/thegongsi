"use client";

import { useEffect, useState } from "react";

const KEY = "comad_stock_theme";

export function ThemeToggle() {
  // 초기 렌더는 layout의 inline script가 이미 DOM에 테마를 적용한 상태
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const current = (document.documentElement.getAttribute("data-theme") as "dark" | "light") || "dark";
    setTheme(current);
    setMounted(true);
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem(KEY, next);
    document.documentElement.setAttribute("data-theme", next);
  }

  return (
    <button
      onClick={toggle}
      className="mono text-[12px] text-fg-3 hover:text-fg transition-colors"
      aria-label="Toggle theme"
    >
      {mounted ? (theme === "dark" ? "☾" : "☀") : "☾"}
    </button>
  );
}
