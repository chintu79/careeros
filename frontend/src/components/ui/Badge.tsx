import React from 'react';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'neutral' | 'emerald' | 'amber' | 'rose' | 'sky' | 'outline';
  size?: 'sm' | 'md';
  dot?: boolean;
  icon?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'neutral',
  size = 'md',
  dot = false,
  icon,
  children,
  className = '',
  ...props
}) => {
  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-[10px] gap-1 rounded-[var(--radius-xs)]',
    md: 'px-2 py-0.5 text-[11px] gap-1.5 rounded-[var(--radius-xs)]',
  }[size];

  const variantClasses = {
    default: 'border-[var(--color-accent-border)] bg-[var(--color-accent-bg)] text-[var(--color-accent)]',
    neutral: 'border-[var(--color-rule-2)] bg-[var(--color-paper-3)] text-[var(--color-ink-2)]',
    emerald: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-400',
    amber: 'border-amber-500/25 bg-amber-500/10 text-amber-400',
    rose: 'border-rose-500/25 bg-rose-500/10 text-rose-400',
    sky: 'border-sky-500/25 bg-sky-500/10 text-sky-400',
    outline: 'border-[var(--color-rule-2)] bg-transparent text-[var(--color-ink-2)]',
  }[variant];

  const dotClasses = {
    default: 'bg-[var(--color-accent)]',
    neutral: 'bg-[var(--color-muted)]',
    emerald: 'bg-emerald-400',
    amber: 'bg-amber-400',
    rose: 'bg-rose-400',
    sky: 'bg-sky-400',
    outline: 'bg-[var(--color-ink-2)]',
  }[variant];

  return (
    <span
      className={`inline-flex select-none items-center border font-mono font-medium tnum ${sizeClasses} ${variantClasses} ${className}`}
      {...props}
    >
      {dot && (
        <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${dotClasses}`} aria-hidden="true" />
      )}
      {icon && <span className="shrink-0" aria-hidden="true">{icon}</span>}
      <span>{children}</span>
    </span>
  );
};

