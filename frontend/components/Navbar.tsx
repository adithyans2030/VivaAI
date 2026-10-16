"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, User } from "@/lib/api";
import BrandLogo from "@/components/BrandLogo";
import ThemeToggle from "@/components/ThemeToggle";
import { Mic, LayoutDashboard, LogOut, Palette, LogIn } from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const cached = localStorage.getItem("vivaiq_user");
    if (cached) {
      try {
        setUser(JSON.parse(cached));
      } catch {
        // ignore
      }
    }
    api.getMe().then(setUser).catch(() => {});
  }, [pathname]);

  const handleLogout = () => {
    api.clearToken();
    setUser(null);
    router.push("/login");
  };

  // Hide standalone navbar on the split-screen login page
  if (pathname === "/login") return null;

  return (
    <header className="sticky top-0 z-50 bg-[var(--bg-surface)]/90 backdrop-blur-md border-b border-[var(--border-default)] px-6 py-3.5 transition-colors">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand */}
        <BrandLogo href="/" />

        {/* Navigation Pills */}
        <nav className="hidden md:flex items-center gap-1 bg-[var(--bg-card-subtle)] p-1 rounded-xl border border-[var(--border-default)]">
          <Link
            href="/student"
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              pathname.startsWith("/student")
                ? "bg-[var(--accent-primary)] text-[var(--accent-contrast)] shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]"
            }`}
          >
            <Mic className="w-3.5 h-3.5" />
            Student Viva
          </Link>

          <Link
            href="/teacher"
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              pathname.startsWith("/teacher")
                ? "bg-[var(--accent-primary)] text-[var(--accent-contrast)] shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]"
            }`}
          >
            <LayoutDashboard className="w-3.5 h-3.5" />
            Teacher Review
          </Link>

          <Link
            href="/design-system"
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              pathname === "/design-system"
                ? "bg-[var(--accent-primary)] text-[var(--accent-contrast)] shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]"
            }`}
          >
            <Palette className="w-3.5 h-3.5" />
            Design System
          </Link>
        </nav>

        {/* User Status / Theme Switcher */}
        <div className="flex items-center gap-3">
          <ThemeToggle />

          {user ? (
            <div className="flex items-center gap-2">
              <span className="hidden sm:inline-block text-xs font-medium text-[var(--text-secondary)]">
                {user.full_name}
              </span>
              <button
                onClick={handleLogout}
                aria-label="Log out"
                className="p-2 rounded-xl text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-subtle)] transition-colors cursor-pointer"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="flex items-center gap-1.5 text-xs font-semibold text-[var(--text-primary)] px-3 py-1.5 rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] hover:bg-[var(--bg-card-subtle)] transition-colors"
            >
              <LogIn className="w-3.5 h-3.5" />
              Sign In
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
