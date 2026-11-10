import React, { useRef } from 'react';

export interface TabItem {
  id: string;
  label: React.ReactNode;
  icon?: React.ReactNode;
  count?: number;
  disabled?: boolean;
}

export interface TabsProps {
  items: TabItem[];
  active: string;
  onChange: (id: string) => void;
  variant?: 'underline' | 'segmented';
  ariaLabel?: string;
  size?: 'sm' | 'md';
  className?: string;
}

export const Tabs: React.FC<TabsProps> = ({
  items,
  active,
  onChange,
  variant = 'underline',
  ariaLabel = 'Views',
  size = 'md',
  className = '',
}) => {
  const tabListRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    let nextIndex = -1;
    if (e.key === 'ArrowRight') {
      nextIndex = (index + 1) % items.length;
    } else if (e.key === 'ArrowLeft') {
      nextIndex = (index - 1 + items.length) % items.length;
    } else if (e.key === 'Home') {
      nextIndex = 0;
    } else if (e.key === 'End') {
      nextIndex = items.length - 1;
    }

    if (nextIndex !== -1) {
      e.preventDefault();
      const nextTab = items[nextIndex];
      if (!nextTab.disabled) {
        onChange(nextTab.id);
        const buttons = tabListRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
        buttons?.[nextIndex]?.focus();
      }
    }
  };

  if (variant === 'segmented') {
    return (
      <div
        ref={tabListRef}
        role="tablist"
        aria-label={ariaLabel}
        className={`inline-flex items-center gap-1 rounded-[var(--radius-control)] border border-[var(--color-rule-2)] bg-[var(--color-paper-2)] p-1 ${className}`}
      >
        {items.map((item, idx) => {
          const isActive = item.id === active;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              id={`tab-${item.id}`}
              aria-selected={isActive}
              tabIndex={isActive ? 0 : -1}
              disabled={item.disabled}
              onClick={() => onChange(item.id)}
              onKeyDown={(e) => handleKeyDown(e, idx)}
              className={`inline-flex items-center gap-1.5 rounded-[var(--radius-xs)] px-2.5 py-1 text-[12px] font-medium transition-colors focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--color-focus)] disabled:opacity-40 ${
                isActive
                  ? 'bg-[var(--color-paper-4)] text-[var(--color-ink)] shadow-sm'
                  : 'text-[var(--color-ink-2)] hover:bg-[var(--color-paper-3)] hover:text-[var(--color-ink)]'
              }`}
            >
              {item.icon && <span aria-hidden="true" className="shrink-0">{item.icon}</span>}
              <span>{item.label}</span>
              {typeof item.count === 'number' && (
                <span
                  className={`font-mono text-[10px] tnum rounded px-1.5 py-0.5 ${
                    isActive
                      ? 'bg-[var(--color-accent-bg)] text-[var(--color-accent)]'
                      : 'bg-[var(--color-paper-3)] text-[var(--color-muted)]'
                  }`}
                >
                  {item.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      ref={tabListRef}
      role="tablist"
      aria-label={ariaLabel}
      className={`flex items-center gap-6 overflow-x-auto no-scrollbar border-b border-[var(--color-rule-2)] ${className}`}
    >
      {items.map((item, idx) => {
        const isActive = item.id === active;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            disabled={item.disabled}
            onClick={() => onChange(item.id)}
            onKeyDown={(e) => handleKeyDown(e, idx)}
            className={`group relative inline-flex items-center gap-2 pb-3 pt-1 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] disabled:opacity-40 ${
              isActive
                ? 'text-[var(--color-ink)]'
                : 'text-[var(--color-ink-2)] hover:text-[var(--color-ink)]'
            }`}
          >
            {item.icon && (
              <span
                aria-hidden="true"
                className={`shrink-0 transition-colors ${
                  isActive ? 'text-[var(--color-accent)]' : 'text-[var(--color-muted)] group-hover:text-[var(--color-ink-2)]'
                }`}
              >
                {item.icon}
              </span>
            )}
            <span>{item.label}</span>
            {typeof item.count === 'number' && (
              <span
                className={`font-mono text-[11px] tnum rounded px-1.5 py-0.5 ${
                  isActive
                    ? 'bg-[var(--color-accent-bg)] text-[var(--color-accent)] font-semibold'
                    : 'bg-[var(--color-paper-3)] text-[var(--color-muted)]'
                }`}
              >
                {item.count}
              </span>
            )}

            {isActive && (
              <span
                aria-hidden="true"
                className="absolute inset-x-0 bottom-0 h-0.5 bg-[var(--color-accent)] shadow-[0_-1px_4px_var(--color-accent-shadow)]"
              />
            )}
          </button>
        );
      })}
    </div>
  );
};
