"use client";

import React from "react";
import { useTheme } from "@/components/ThemeProvider";
import { Moon, Sun } from "lucide-react";

interface ThemeToggleProps {
  className?: string;
}

export default function ThemeToggle({ className = "" }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      type="button"
      aria-label="Toggle theme"
      className={`w-10 h-10 rounded-full flex items-center justify-center transition-all cursor-pointer border border-border-default bg-bg-card hover:bg-bg-card-subtle text-text-secondary hover:text-text-primary shadow-sm ${className}`}
    >
      {theme === "dark" ? (
        <Sun className="w-4 h-4 text-text-secondary hover:text-text-primary transition-colors" />
      ) : (
        <Moon className="w-4 h-4 text-text-secondary hover:text-text-primary transition-colors" />
      )}
    </button>
  );
}
