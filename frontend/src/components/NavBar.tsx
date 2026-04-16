"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ThemeToggle } from "./ThemeToggle";

const TOKEN_KEY = "comad_stock_token";

const LINKS = [
  { href: "/", label: "home" },
  { href: "/ask", label: "ask" },
  { href: "/watchlist", label: "watchlist" },
  { href: "/settings", label: "settings" },
];

export function NavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const [authed, setAuthed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const sync = () => setAuthed(Boolean(localStorage.getItem(TOKEN_KEY)));
    sync();
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, [pathname]);

  // 라우트 변경 시 모바일 메뉴 닫기
  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setAuthed(false);
    router.push("/");
  }

  return (
    <nav className="border-b border-border/50">
      <div className="mx-auto max-w-[1280px] flex items-center justify-between px-6 sm:px-8 py-5">
        <Link href="/" className="font-serif text-[18px] tracking-tight text-fg">
          The Gongsi
        </Link>

        {/* Desktop menu */}
        <ul className="hidden md:flex items-center gap-8">
          {LINKS.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                aria-current={pathname === l.href ? "page" : undefined}
                className={`mono text-[13px] transition-colors ${
                  pathname === l.href ? "text-accent" : "text-fg-2 hover:text-fg"
                }`}
              >
                {l.label}
              </Link>
            </li>
          ))}
          {authed ? (
            <li>
              <button
                onClick={logout}
                className="mono text-[13px] text-fg-3 hover:text-sev-high transition-colors"
              >
                logout
              </button>
            </li>
          ) : (
            <li>
              <Link
                href="/login"
                className="mono text-[13px] text-accent border-b border-accent"
              >
                login →
              </Link>
            </li>
          )}
          <li>
            <ThemeToggle />
          </li>
        </ul>

        {/* Mobile hamburger */}
        <div className="md:hidden flex items-center gap-4">
          <ThemeToggle />
          <button
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
            aria-controls="mobile-menu"
            aria-label={menuOpen ? "메뉴 닫기" : "메뉴 열기"}
            className="mono text-[14px] text-fg-2 hover:text-fg p-2"
          >
            {menuOpen ? "✕" : "≡"}
          </button>
        </div>
      </div>

      {/* Mobile menu panel */}
      {menuOpen && (
        <ul id="mobile-menu" className="md:hidden border-t border-border/50 px-6 py-4 space-y-3">
          {LINKS.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                aria-current={pathname === l.href ? "page" : undefined}
                className={`mono text-[14px] block py-1 transition-colors ${
                  pathname === l.href ? "text-accent" : "text-fg-2 hover:text-fg"
                }`}
              >
                {l.label}
              </Link>
            </li>
          ))}
          {authed ? (
            <li>
              <button
                onClick={logout}
                className="mono text-[14px] text-fg-3 hover:text-sev-high transition-colors py-1"
              >
                logout
              </button>
            </li>
          ) : (
            <li>
              <Link
                href="/login"
                className="mono text-[14px] text-accent border-b border-accent inline-block"
              >
                login →
              </Link>
            </li>
          )}
        </ul>
      )}
    </nav>
  );
}
