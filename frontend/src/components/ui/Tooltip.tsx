import React, { useState, useRef, useId } from 'react';

export interface TooltipProps {
  content: React.ReactNode;
  shortcut?: string;
  side?: 'top' | 'bottom' | 'left' | 'right';
  children: React.ReactElement;
  delay?: number;
  className?: string;
}

export const Tooltip: React.FC<TooltipProps> = ({
  content,
  shortcut,
  side = 'top',
  children,
  delay = 150,
  className = '',
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tooltipId = useId();

  const show = () => {
    timeoutRef.current = setTimeout(() => {
      setIsVisible(true);
    }, delay);
  };

  const hide = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setIsVisible(false);
  };

  const sideClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-1.5',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-1.5',
    left: 'right-full top-1/2 -translate-y-1/2 mr-1.5',
    right: 'left-full top-1/2 -translate-y-1/2 ml-1.5',
  }[side];

  return (
    <div
      className="relative inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {React.cloneElement(children, {
        'aria-describedby': isVisible ? tooltipId : undefined,
      })}

      {isVisible && (
        <div
          id={tooltipId}
          role="tooltip"
          className={`pointer-events-none absolute z-[var(--z-tooltip)] flex items-center gap-1.5 whitespace-nowrap rounded-[var(--radius-xs)] border border-[var(--color-rule)] bg-[var(--color-paper-4)] px-2 py-0.5 text-[11px] font-medium text-[var(--color-ink)] shadow-dropdown animate-fade-in ${sideClasses} ${className}`}
        >
          <span>{content}</span>
          {shortcut && (
            <kbd className="rounded border border-[var(--color-rule-2)] bg-[var(--color-paper-2)] px-1 py-px font-mono text-[9px] text-[var(--color-muted)]">
              {shortcut}
            </kbd>
          )}
        </div>
      )}
    </div>
  );
};
