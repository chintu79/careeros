import React, { forwardRef } from 'react';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'xs' | 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantClasses: Record<NonNullable<ButtonProps['variant']>, string> = {
  primary: 'border border-[var(--color-accent)] bg-[var(--color-accent)] text-[var(--color-accent-ink)] font-medium hover:bg-[var(--color-accent-hover)] hover:border-[var(--color-accent-hover)] shadow-sm active:translate-y-px',
  secondary: 'border border-[var(--color-rule-2)] bg-[var(--color-paper-3)] text-[var(--color-ink)] hover:bg-[var(--color-hover)] hover:border-[var(--color-rule)] active:translate-y-px',
  outline: 'border border-[var(--color-rule-2)] bg-transparent text-[var(--color-ink-2)] hover:border-[var(--color-rule)] hover:bg-[var(--color-hover)] hover:text-[var(--color-ink)] active:translate-y-px',
  ghost: 'border border-transparent bg-transparent text-[var(--color-ink-2)] hover:bg-[var(--color-hover)] hover:text-[var(--color-ink)] active:translate-y-px',
  danger: 'border border-red-500/20 bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:border-red-500/30 active:translate-y-px',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({
  variant = 'secondary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  children,
  className = '',
  disabled,
  type = 'button',
  ...props
}, ref) => {
  const sizeClasses = {
    xs: 'px-2 py-1 text-[11px] gap-1 min-h-[28px] rounded-[var(--radius-xs)]',
    sm: 'px-2.5 py-1.5 text-[12px] gap-1.5 min-h-[32px] rounded-[var(--radius-sm)]',
    md: 'px-3.5 py-1.5 text-[13px] gap-2 min-h-[36px] rounded-[var(--radius-control)]',
    lg: 'px-4 py-2 text-[14px] gap-2 min-h-[40px] rounded-[var(--radius-standard)]',
  }[size];

  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || isLoading}
      aria-busy={isLoading}
      className={`inline-flex select-none items-center justify-center gap-1.5 font-sans font-medium transition-colors duration-[var(--dur-micro)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] disabled:pointer-events-none disabled:opacity-40 disabled:cursor-not-allowed ${sizeClasses} ${variantClasses[variant]} ${className}`}
      {...props}
    >
      {isLoading ? (
        <>
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden="true" />
          <span className="sr-only">Loading…</span>
        </>
      ) : (
        leftIcon && <span className="shrink-0" aria-hidden="true">{leftIcon}</span>
      )}
      <span>{children}</span>
      {!isLoading && rightIcon && <span className="shrink-0" aria-hidden="true">{rightIcon}</span>}
    </button>
  );
});

Button.displayName = 'Button';

