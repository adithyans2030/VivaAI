"use client";

import React, { forwardRef } from "react";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, className = "", id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="w-full space-y-1.5 text-left">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-xs md:text-sm font-medium text-[var(--text-secondary)]"
          >
            {label}
          </label>
        )}
        <div className="relative">
          <input
            id={inputId}
            ref={ref}
            className={`w-full px-4 py-3 text-sm rounded-xl transition-all outline-none border bg-[var(--bg-card)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--border-focus)] focus:ring-1 focus:ring-[var(--border-focus)] ${
              error
                ? "border-[var(--error-border)] focus:border-[var(--error-text)] focus:ring-[var(--error-text)]"
                : "border-[var(--border-default)]"
            } ${className}`}
            {...props}
          />
        </div>
        {error && (
          <p className="text-xs text-[var(--error-text)] mt-1 animate-in fade-in duration-150">
            {error}
          </p>
        )}
        {helperText && !error && (
          <p className="text-xs text-[var(--text-muted)] mt-1">{helperText}</p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
export default Input;
