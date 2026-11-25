import React, { forwardRef } from "react";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  icon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, icon, className = "", id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="w-full space-y-2 text-left">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-xs font-semibold tracking-wide text-[var(--text-secondary)] uppercase"
          >
            {label}
          </label>
        )}
        <div className="relative group">
          {icon && (
            <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] group-focus-within:text-[var(--accent-1)] transition-colors duration-200 pointer-events-none">
              {icon}
            </div>
          )}
          <input
            id={inputId}
            ref={ref}
            className={[
              "w-full py-3 text-sm rounded-xl transition-all duration-200 outline-none",
              "bg-[var(--bg-card)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)]",
              "border border-[var(--border-default)]",
              "focus:border-[var(--accent-1)] focus:ring-2 focus:ring-[var(--accent-1)]/20",
              "hover:border-[var(--border-emphasis)]",
              icon ? "pl-10 pr-4" : "px-4",
              error
                ? "border-[var(--error-border)] focus:border-[var(--error)] focus:ring-[var(--error)]/20"
                : "",
              className,
            ].join(" ")}
            {...props}
          />
          {/* Focus glow */}
          <div className="absolute inset-0 rounded-xl ring-2 ring-[var(--accent-1)]/0 group-focus-within:ring-[var(--accent-1)]/10 pointer-events-none transition-all duration-200" />
        </div>
        {error && (
          <p className="text-xs text-[var(--error-text)] flex items-center gap-1.5 animate-fade-in-up">
            <span className="w-1 h-1 rounded-full bg-current inline-block" />
            {error}
          </p>
        )}
        {helperText && !error && (
          <p className="text-xs text-[var(--text-muted)]">{helperText}</p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
export default Input;
