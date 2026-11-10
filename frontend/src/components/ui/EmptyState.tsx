import React from 'react';

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  secondaryAction?: React.ReactNode;
  compact?: boolean;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  secondaryAction,
  compact = false,
  className = '',
}) => {
  return (
    <div
      className={`text-center flex flex-col items-center justify-center rounded-[var(--radius-card)] border border-dashed border-[var(--color-rule-2)] bg-[var(--color-paper-2)]/60 ${
        compact ? 'p-6 sm:p-8' : 'p-10 sm:p-14'
      } ${className}`}
    >
      {icon && (
        <div className="w-11 h-11 rounded-[var(--radius-control)] bg-[var(--color-paper-3)] border border-[var(--color-rule-2)] flex items-center justify-center text-[var(--color-muted)] mb-3.5 shadow-sm">
          {icon}
        </div>
      )}
      <h3 className="text-[14px] font-semibold text-[var(--color-ink)]">{title}</h3>
      <p className="text-[12px] text-[var(--color-ink-2)] mt-1.5 max-w-md mx-auto leading-relaxed">
        {description}
      </p>
      {(action || secondaryAction) && (
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2.5">
          {action}
          {secondaryAction}
        </div>
      )}
    </div>
  );
};
