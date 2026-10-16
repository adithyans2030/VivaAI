"use client";

import React from "react";

interface BadgeProps {
  variant?: "default" | "success" | "warning" | "error" | "eyebrow" | "advisory";
  children: React.ReactNode;
  className?: string;
  icon?: React.ReactNode;
}

export default function Badge({
  variant = "default",
  icon,
  children,
  className = "",
}: BadgeProps) {
  const baseStyles = "inline-flex items-center gap-1.5 font-medium transition-colors";

  const variantStyles = {
    default:
      "px-2.5 py-1 text-xs rounded-lg bg-[var(--bg-card-subtle)] text-[var(--text-secondary)] border border-[var(--border-default)]",
    success:
      "px-2.5 py-1 text-xs rounded-lg bg-emerald-500/10 text-emerald-500 border border-emerald-500/20",
    warning:
      "px-2.5 py-1 text-xs rounded-lg bg-amber-500/10 text-amber-500 border border-amber-500/20",
    error:
      "px-2.5 py-1 text-xs rounded-lg bg-[var(--error-bg)] text-[var(--error-text)] border border-[var(--error-border)]",
    eyebrow:
      "text-[10px] md:text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-secondary)]",
    advisory:
      "text-xs text-[var(--text-secondary)] gap-2",
  }[variant];

  return (
    <span className={`${baseStyles} ${variantStyles} ${className}`}>
      {icon}
      {children}
    </span>
  );
}
