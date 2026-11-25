import React from "react";
import { Loader2 } from "lucide-react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
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
  const base =
    "inline-flex items-center justify-center font-semibold rounded-xl transition-all duration-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] focus-visible:ring-offset-2 active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none select-none";

  const sizes = {
    sm: "px-3.5 py-1.5 text-xs gap-1.5",
    md: "px-5 py-2.5 text-sm gap-2",
    lg: "px-6 py-3 text-[15px] gap-2.5",
  }[size];

  const variants: Record<string, string> = {
    primary: [
      "text-[var(--bg-base)] relative overflow-hidden",
      "before:absolute before:inset-0 before:opacity-0 before:transition-opacity before:duration-200 hover:before:opacity-100 before:bg-white/10",
    ].join(" "),
    secondary:
      "bg-[var(--bg-card)] border border-[var(--border-emphasis)] text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)] hover:border-[var(--accent-1)] shadow-sm",
    outline:
      "bg-transparent border border-[var(--border-default)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-emphasis)] hover:bg-[var(--bg-card)]",
    ghost:
      "bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]",
    danger:
      "bg-[var(--error-bg)] border border-[var(--error-border)] text-[var(--error-text)] hover:bg-[rgba(255,77,109,0.15)]",
  };

  const primaryStyle =
    variant === "primary"
      ? {
          background: "linear-gradient(135deg, var(--accent-1), var(--accent-2))",
          boxShadow: "0 0 20px rgba(74, 158, 255, 0.35), 0 2px 8px rgba(0,0,0,0.3)",
        }
      : {};

  return (
    <button
      disabled={disabled || isLoading}
      className={`${base} ${sizes} ${variants[variant]} ${className}`}
      style={primaryStyle}
      {...props}
    >
      {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
      {children}
    </button>
  );
}
