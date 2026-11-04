"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, User } from "@/lib/api";
import BrandLogo from "@/components/BrandLogo";
import ThemeToggle from "@/components/ThemeToggle";
import { Mic, LayoutDashboard, LogOut, LogIn } from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // Show the cached user immediately, then confirm against the API. Visitors without a
    // token are left alone, so public pages never bounce to /login on a 401.
    Promise.resolve()
      .then(() => {
        if (!localStorage.getItem("vivaiq_token")) {
          if (!cancelled) setUser(null);
          return null;
        }
        const cached = localStorage.getItem("vivaiq_user");
        if (cached && !cancelled) setUser(JSON.parse(cached) as User);
        return api.getMe();
      })
      .then((me) => {
        if (!cancelled && me) setUser(me);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const handleLogout = async () => {
    await api.logout();
    setUser(null);
    router.push("/login");
  };

  if (pathname === "/login") return null;

  // Each role only sees the workspace it can use; admins see both.
  const navLinks = [
    { href: "/student", label: "Student Viva", icon: Mic, match: "/student", roles: ["student", "admin"] },
    { href: "/teacher", label: "Teacher Portal", icon: LayoutDashboard, match: "/teacher", roles: ["teacher", "admin"] },
  ].filter((link) => user && link.roles.includes(user.role));

  const nav = (className: string) =>
    navLinks.length > 1 && (
      <nav
        aria-label="Primary"
        className={`${className} items-center gap-1 bg-[var(--bg-card)]/70 border border-[var(--border-subtle)] backdrop-blur-md rounded-2xl p-1`}
      >
        {navLinks.map(({ href, label, icon: Icon, match }) => {
          const active = pathname.startsWith(match);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`flex flex-1 justify-center items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all duration-200 ${
                active
                  ? "bg-[var(--accent-1)] text-white shadow-[0_0_12px_rgba(74,158,255,0.4)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)]"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </Link>
          );
        })}
      </nav>
    );

  return (
    <header
      className={`sticky top-0 z-50 transition-all duration-300 ${
        scrolled
          ? "bg-[var(--bg-base)]/90 backdrop-blur-xl border-b border-[var(--border-default)] shadow-[0_4px_24px_-4px_rgba(0,0,0,0.5)]"
          : "bg-transparent border-b border-transparent"
      }`}
    >
      <div className="max-w-7xl mx-auto px-5 py-3.5 flex items-center justify-between gap-4">
        {/* Brand */}
        <BrandLogo href="/" />

        {/* Center nav */}
        {nav("hidden md:flex")}

        {/* Right side */}
        <div className="flex items-center gap-2.5">
          <ThemeToggle />

          {user ? (
            <div className="flex items-center gap-2">
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)]">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-[var(--accent-1)] to-[var(--accent-2)] flex items-center justify-center text-[10px] font-bold text-[var(--bg-base)]">
                  {user.full_name?.[0]?.toUpperCase() ?? "U"}
                </div>
                <span className="text-xs font-medium text-[var(--text-secondary)] max-w-[120px] truncate">
                  {user.full_name}
                </span>
              </div>
              <button
                onClick={handleLogout}
                aria-label="Log out"
                className="p-2 rounded-xl text-[var(--text-muted)] hover:text-[var(--error-text)] hover:bg-[var(--error-bg)] transition-all duration-200 cursor-pointer"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="flex items-center gap-1.5 text-xs font-semibold text-white px-4 py-2 rounded-xl transition-all duration-200"
              style={{
                background: "linear-gradient(135deg, #4a9eff, #3bf0aa)",
                boxShadow: "0 0 16px rgba(74, 158, 255, 0.3)",
              }}
            >
              <LogIn className="w-3.5 h-3.5" />
              Sign In
            </Link>
          )}
        </div>
      </div>
      {nav("flex md:hidden mx-5 mb-3")}
    </header>
  );
}
