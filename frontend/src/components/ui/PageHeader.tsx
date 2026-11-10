import React from 'react';

export interface PageHeaderProps {
  eyebrow?: string;
  title: React.ReactNode;
  description?: React.ReactNode;
  meta?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

/**
 * The one page-level masthead. The app header only carries breadcrumbs; the
 * page itself owns its h1, its lede and its primary action.
 */
export const PageHeader: React.FC<PageHeaderProps> = ({
  eyebrow,
  title,
  description,
  meta,
  actions,
  className = '',
}) => {
  return (
    <header className={`flex flex-col gap-4 pb-5 border-b border-[var(--color-rule-2)] sm:flex-row sm:items-end sm:justify-between ${className}`}>
      <div className="min-w-0 space-y-1.5">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h1 className="page-title">{title}</h1>
          {meta}
        </div>
        {description && <p className="page-lede max-w-2xl">{description}</p>}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {actions}
        </div>
      )}
    </header>
  );
};

export interface StatTileProps {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  icon?: React.ReactNode;
  onClick?: () => void;
  active?: boolean;
  className?: string;
}

/**
 * Flat KPI tile. Equal weight for every metric — the number carries the
 * emphasis, not a colour or an icon badge.
 */
export const StatTile: React.FC<StatTileProps> = ({
  label,
  value,
  hint,
  icon,
  onClick,
  active = false,
  className = '',
}) => {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      {...(onClick ? { type: 'button' as const, onClick } : {})}
      className={`group flex min-w-0 flex-col items-start rounded-[var(--radius-standard)] border shadow-card px-4 py-3.5 text-left transition-colors ${
        active
          ? 'border-[var(--color-accent-border)] bg-[var(--color-paper-3)]'
          : 'border-[var(--color-rule-2)] bg-[var(--color-paper-2)]'
      } ${onClick ? 'hover:border-[var(--color-rule)] hover:bg-[var(--color-hover)] cursor-pointer focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]' : ''} ${className}`}
    >
      <div className="flex w-full items-center justify-between gap-2">
        <span className="field-label">{label}</span>
        {icon && (
          <span className={`shrink-0 transition-colors ${active ? 'text-[var(--color-ink)]' : 'text-[var(--color-muted)] group-hover:text-[var(--color-ink)]'}`} aria-hidden="true">
            {icon}
          </span>
        )}
      </div>
      <span className="stat-value mt-1.5 text-[26px]">
        {value}
      </span>
      {hint && <span className="mt-1.5 text-[11px] leading-tight text-[var(--color-ink-2)]">{hint}</span>}
    </Tag>
  );
};
export { Tabs, type TabItem, type TabsProps } from './Tabs';

