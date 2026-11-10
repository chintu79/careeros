import React, { forwardRef, useId } from 'react';
import { X } from 'lucide-react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  shortcut?: string;
  error?: string;
  onClear?: () => void;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({
  label,
  leftIcon,
  rightIcon,
  shortcut,
  error,
  onClear,
  value,
  id,
  className = '',
  required,
  ...props
}, ref) => {
  const generatedId = useId();
  const inputId = id || generatedId;
  const errorId = `${inputId}-error`;
  return (
    <div className="w-full space-y-1.5">
      {label && (
        <label htmlFor={inputId} className="field-label block">
          {label}
          {required && <span className="ml-0.5 text-[var(--color-ink)]" aria-hidden="true">*</span>}
        </label>
      )}

      <div className="relative flex w-full items-center">
        {leftIcon && (
          <span className="pointer-events-none absolute left-3 flex shrink-0 items-center text-[var(--color-muted)]" aria-hidden="true">
            {leftIcon}
          </span>
        )}

        <input
          ref={ref}
          id={inputId}
          value={value}
          required={required}
          aria-invalid={!!error}
          aria-describedby={error ? errorId : props['aria-describedby']}
          className={`min-h-[36px] w-full rounded-[var(--radius-control)] border bg-[var(--color-paper-2)] py-1.5 font-sans text-[13px] text-[var(--color-ink)] transition-colors placeholder:text-[var(--color-muted)] focus:outline-none focus:outline-2 focus:outline-offset-[-1px] focus:outline-[var(--color-focus)] focus:border-[var(--color-focus)] ${
            leftIcon ? 'pl-9' : 'pl-3'
          } ${
            rightIcon || shortcut || onClear ? 'pr-9' : 'pr-3'
          } ${
            error
              ? 'border-red-500/50 bg-red-500/[0.03]'
              : 'border-[var(--color-rule-2)] hover:border-[var(--color-rule)]'
          } ${className}`}
          {...props}
        />

        <div className="absolute right-2.5 flex items-center gap-1.5">
          {onClear && value && (
            <button
              type="button"
              onClick={onClear}
              className="rounded-[var(--radius-xs)] p-1 text-[var(--color-muted)] transition-colors hover:bg-[var(--color-hover)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              aria-label="Clear input"
            >
              <X className="h-3 h-3" aria-hidden="true" />
            </button>
          )}

          {shortcut && !value && (
            <kbd className="hidden select-none items-center rounded-[var(--radius-xs)] border border-[var(--color-rule-2)] bg-[var(--color-paper-3)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--color-muted)] sm:inline-flex" aria-hidden="true">
              {shortcut}
            </kbd>
          )}

          {rightIcon && !onClear && !shortcut && (
            <span className="text-[var(--color-muted)]" aria-hidden="true">{rightIcon}</span>
          )}
        </div>
      </div>

      {error && (
        <p id={errorId} role="alert" className="pl-0.5 text-[11px] font-medium text-red-400">
          {error}
        </p>
      )}
    </div>
  );
});

Input.displayName = 'Input';
