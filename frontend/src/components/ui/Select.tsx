import React, { forwardRef, useId } from 'react';
import { ChevronDown } from 'lucide-react';

export interface SelectOption {
  value: string | number;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options?: SelectOption[];
  error?: string;
  hint?: string;
  leftIcon?: React.ReactNode;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(({
  label,
  options,
  error,
  hint,
  leftIcon,
  id,
  className = '',
  required,
  children,
  value,
  ...props
}, ref) => {
  const generatedId = useId();
  const selectId = id || generatedId;
  const errorId = `${selectId}-error`;
  const hintId = `${selectId}-hint`;

  return (
    <div className="w-full space-y-1.5">
      {label && (
        <label htmlFor={selectId} className="field-label block">
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

        <select
          ref={ref}
          id={selectId}
          value={value}
          required={required}
          aria-invalid={!!error}
          aria-describedby={error ? errorId : hint ? hintId : props['aria-describedby']}
          className={`min-h-[36px] w-full appearance-none rounded-[var(--radius-control)] border bg-[var(--color-paper-2)] py-1.5 pr-8 font-sans text-[13px] text-[var(--color-ink)] transition-colors focus:outline-none focus:outline-2 focus:outline-offset-[-1px] focus:outline-[var(--color-focus)] focus:border-[var(--color-focus)] ${
            leftIcon ? 'pl-9' : 'pl-3'
          } ${
            error
              ? 'border-red-500/50 bg-red-500/[0.03]'
              : 'border-[var(--color-rule-2)] hover:border-[var(--color-rule)]'
          } ${className}`}
          {...props}
        >
          {options
            ? options.map(opt => (
                <option
                  key={opt.value}
                  value={opt.value}
                  disabled={opt.disabled}
                  className="bg-[var(--color-paper-2)] text-[var(--color-ink)] py-1"
                >
                  {opt.label}
                </option>
              ))
            : children}
        </select>

        <span className="pointer-events-none absolute right-2.5 flex shrink-0 items-center text-[var(--color-muted)]" aria-hidden="true">
          <ChevronDown className="h-3.5 w-3.5" />
        </span>
      </div>

      {error && (
        <p id={errorId} role="alert" className="pl-0.5 text-[11px] font-medium text-red-400">
          {error}
        </p>
      )}

      {hint && !error && (
        <p id={hintId} className="pl-0.5 text-[11px] text-[var(--color-muted)]">
          {hint}
        </p>
      )}
    </div>
  );
});

Select.displayName = 'Select';
