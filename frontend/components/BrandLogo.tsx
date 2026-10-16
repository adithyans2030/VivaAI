import React from "react";
import Link from "next/link";

interface BrandLogoProps {
  className?: string;
  size?: "sm" | "md" | "lg";
  href?: string;
}

export default function BrandLogo({ className = "", size = "md", href = "/" }: BrandLogoProps) {
  const badgeSize = {
    sm: "w-7 h-7 text-xs rounded-lg",
    md: "w-8 h-8 text-sm rounded-xl",
    lg: "w-10 h-10 text-base rounded-xl",
  }[size];

  const content = (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <div
        className={`${badgeSize} flex items-center justify-center font-bold font-sans bg-[var(--logo-bg)] text-[var(--logo-fg)] shadow-xs transition-colors`}
      >
        v
      </div>
      <div className="flex flex-col leading-tight">
        <span className="font-semibold text-sm tracking-tight text-[var(--text-primary)]">
          VivaIQ
        </span>
        <span className="text-[9px] font-semibold tracking-[0.16em] uppercase text-[var(--text-muted)]">
          A Fairer Viva
        </span>
      </div>
    </div>
  );

  if (href) {
    return <Link href={href} className="inline-block hover:opacity-90 transition-opacity">{content}</Link>;
  }

  return content;
}
