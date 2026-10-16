"use client";

import React from "react";
import { Loader2 } from "lucide-react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "outline" | "ghost";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
  children: React.ReactNode;
}

export default function Button({
  variant = "primary",
  size = "md",
  isLoading = false,
  disabled,
  children,
  className = "",
  ...props
}: ButtonProps) {
  const baseStyles =
    "inline-flex items-center justify-center font-medium rounded-xl transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-offset-2 active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none";

  const sizeStyles = {
    sm: "px-3.5 py-2 text-xs gap-1.5",
    md: "px-5 py-3 text-sm gap-2",
    lg: "px-6 py-3.5 text-base gap-2.5",
  }[size];

  const variantStyles = {
    primary:
      "bg-[var(--accent-primary)] text-[var(--accent-contrast)] hover:bg-[var(--accent-hover)] font-semibold shadow-sm focus:ring-[var(--border-focus)]",
    outline:
      "bg-[var(--bg-card)] border border-[var(--border-default)] text-[var(--text-primary)] hover:bg-[var(--bg-card-subtle)] focus:ring-[var(--border-focus)] shadow-xs",
    ghost:
      "bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-subtle)]",
  }[variant];

  return (
    <button
      disabled={disabled || isLoading}
      className={`${baseStyles} ${sizeStyles} ${variantStyles} ${className}`}
      {...props}
    >
      {isLoading && <Loader2 className="w-4 h-4 animate-spin text-current" />}
      {children}
    </button>
  );
}
