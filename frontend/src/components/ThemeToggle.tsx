"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

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

  const Icon = !mounted || theme === "dark" ? Moon : Sun;

  return (
    <button
      onClick={toggle}
      className="text-fg-3 hover:text-fg transition-colors p-1 -m-1"
      aria-label={theme === "dark" ? "라이트 모드로" : "다크 모드로"}
      title={theme === "dark" ? "라이트 모드" : "다크 모드"}
    >
      <Icon size={15} strokeWidth={1.75} />
    </button>
  );
}
