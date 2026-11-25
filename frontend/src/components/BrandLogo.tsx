import React from "react";
import { Link } from "react-router";

interface BrandLogoProps {
  className?: string;
  size?: "sm" | "md" | "lg";
  href?: string;
}

export default function BrandLogo({ className = "", size = "md", href = "/" }: BrandLogoProps) {
  const dims = {
    sm: { badge: "w-7 h-7 text-[10px] rounded-[8px]", name: "text-[13px]", tag: "text-[8px]" },
    md: { badge: "w-8 h-8 text-xs rounded-[10px]", name: "text-sm", tag: "text-[9px]" },
    lg: { badge: "w-10 h-10 text-sm rounded-[12px]", name: "text-base", tag: "text-[10px]" },
  }[size];

  const content = (
    <div className={`flex items-center gap-2.5 ${className}`}>
      {/* Badge with gradient */}
      <div
        className={`${dims.badge} flex items-center justify-center font-bold font-mono text-[var(--bg-base)] shrink-0`}
        style={{
          background: "linear-gradient(135deg, #4a9eff 0%, #3bf0aa 100%)",
          boxShadow: "0 0 16px rgba(74, 158, 255, 0.4), 0 2px 8px rgba(0,0,0,0.3)",
        }}
      >
        V
      </div>
      {/* Wordmark */}
      <div className="flex flex-col leading-none gap-0.5">
        <span
          className={`font-bold tracking-tight text-[var(--text-primary)] ${dims.name}`}
          style={{ letterSpacing: "-0.02em" }}
        >
          VivaIQ
        </span>
        <span
          className={`font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)] ${dims.tag}`}
        >
          AI Examiner
        </span>
      </div>
    </div>
  );

  if (href) {
    return (
      <Link to={href} className="inline-block hover:opacity-85 transition-opacity duration-200">
        {content}
      </Link>
    );
  }

  return content;
}
