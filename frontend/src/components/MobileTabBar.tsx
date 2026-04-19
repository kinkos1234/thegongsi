"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, MessageSquare, Bookmark, Settings } from "lucide-react";

/** 모바일 전용 하단 탭바 — 금융 도구 엄지 도달성.
 *
 * md 이상 뷰포트에서는 숨김. safe-area-inset 대응.
 * 네비게이션 계층 얕게 유지: home / ask / watchlist / settings.
 */
const TABS = [
  { href: "/", label: "home", Icon: Home },
  { href: "/ask", label: "ask", Icon: MessageSquare },
  { href: "/watchlist", label: "watchlist", Icon: Bookmark },
  { href: "/settings", label: "settings", Icon: Settings },
];

export function MobileTabBar() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="하단 탭 내비게이션"
      className="md:hidden fixed inset-x-0 bottom-0 z-30 border-t border-border/60 bg-bg/95 backdrop-blur supports-[backdrop-filter]:bg-bg/70"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <ul className="grid grid-cols-4">
        {TABS.map(({ href, label, Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex flex-col items-center justify-center gap-1 py-2.5 transition-colors ${
                  active ? "text-accent" : "text-fg-3 hover:text-fg-2"
                }`}
              >
                <Icon size={18} strokeWidth={1.5} aria-hidden="true" />
                <span className="mono text-[10px] tracking-wider">{label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
