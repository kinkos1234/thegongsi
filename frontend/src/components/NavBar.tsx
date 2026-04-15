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
];

export function NavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    const sync = () => setAuthed(Boolean(localStorage.getItem(TOKEN_KEY)));
    sync();
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, [pathname]);

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setAuthed(false);
    router.push("/");
  }

  return (
    <nav className="border-b border-border/50">
      <div className="mx-auto max-w-[1280px] flex items-center justify-between px-8 py-5">
        <Link href="/" className="mono text-[13px] tracking-wider text-fg">
          COMAD-STOCK
        </Link>
        <ul className="flex items-center gap-8">
          {LINKS.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                className={`mono text-[13px] transition-colors ${
                  pathname === l.href ? "text-accent" : "text-fg-2 hover:text-fg"
                }`}
              >
                {l.label}
              </Link>
            </li>
          ))}
          {authed ? (
            <button
              onClick={logout}
              className="mono text-[13px] text-fg-3 hover:text-sev-high transition-colors"
            >
              logout
            </button>
          ) : (
            <Link
              href="/login"
              className="mono text-[13px] text-accent border-b border-accent"
            >
              login →
            </Link>
          )}
          <li>
            <ThemeToggle />
          </li>
        </ul>
      </div>
    </nav>
  );
}
