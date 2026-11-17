"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, BookOpen, FolderOpen, Users } from "lucide-react";

const items = [
  { href: "/teacher", label: "Viva Sessions", hint: "Review answers & grades", icon: Users },
  { href: "/teacher/materials", label: "Course Material", hint: "Upload notes per subject", icon: FolderOpen },
  { href: "/teacher/subjects", label: "Subjects", hint: "Create & manage courses", icon: BookOpen },
  { href: "/teacher/analytics", label: "Class Analytics", hint: "Averages & flags", icon: BarChart3 },
];

/** A session detail page belongs to "Viva Sessions". */
const isActive = (pathname: string, href: string) =>
  href === "/teacher" ? pathname === "/teacher" || pathname.startsWith("/teacher/sessions") : pathname.startsWith(href);

export default function TeacherNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Teacher workspace">
      {/* Phones/tablets: one scrollable row of tabs */}
      <ul className="flex lg:hidden gap-1.5 overflow-x-auto pb-1 -mx-1 px-1">
        {items.map(({ href, label, icon: Icon }) => {
          const active = isActive(pathname, href);
          return (
            <li key={href} className="shrink-0">
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold border transition-colors ${
                  active
                    ? "bg-[var(--accent-primary)] text-[var(--accent-contrast)] border-transparent"
                    : "bg-[var(--bg-card)] text-[var(--text-secondary)] border-[var(--border-default)] hover:text-[var(--text-primary)]"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>

      {/* Desktop: sticky sidebar */}
      <div className="hidden lg:block sticky top-24">
        <div className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)] px-3 mb-2">
          Teacher Workspace
        </div>
        <ul className="space-y-1">
          {items.map(({ href, label, hint, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-start gap-3 px-3 py-2.5 rounded-xl transition-colors ${
                    active
                      ? "bg-[var(--bg-card)] border border-[var(--border-focus)] text-[var(--text-primary)]"
                      : "border border-transparent text-[var(--text-secondary)] hover:bg-[var(--bg-card)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${active ? "text-[var(--accent-primary)]" : ""}`} />
                  <span>
                    <span className="block text-sm font-semibold">{label}</span>
                    <span className="block text-[11px] text-[var(--text-muted)]">{hint}</span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
