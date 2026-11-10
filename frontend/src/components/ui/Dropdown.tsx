import React, { useState, useRef, useEffect, createContext, useContext } from 'react';

interface DropdownContextType {
  isOpen: boolean;
  setIsOpen: React.Dispatch<React.SetStateAction<boolean>>;
  close: () => void;
}

const DropdownContext = createContext<DropdownContextType | null>(null);

export interface DropdownProps {
  children: React.ReactNode;
  align?: 'left' | 'right';
  className?: string;
}

export const Dropdown: React.FC<DropdownProps> = ({
  children,
  align = 'right',
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const close = () => setIsOpen(false);

  useEffect(() => {
    if (!isOpen) return;

    const handlePointerDown = (e: MouseEvent | TouchEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        close();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        close();
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('touchstart', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('touchstart', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  return (
    <DropdownContext.Provider value={{ isOpen, setIsOpen, close }}>
      <div ref={containerRef} className={`relative inline-block text-left ${className}`}>
        {children}
      </div>
    </DropdownContext.Provider>
  );
};

export interface DropdownTriggerProps {
  children: React.ReactNode;
  asChild?: boolean;
  className?: string;
}

export const DropdownTrigger: React.FC<DropdownTriggerProps> = ({
  children,
  className = '',
}) => {
  const context = useContext(DropdownContext);
  if (!context) throw new Error('DropdownTrigger must be used within Dropdown');

  const { isOpen, setIsOpen } = context;

  return (
    <div
      onClick={() => setIsOpen(!isOpen)}
      aria-haspopup="true"
      aria-expanded={isOpen}
      className={`inline-flex cursor-pointer ${className}`}
    >
      {children}
    </div>
  );
};

export interface DropdownContentProps {
  children: React.ReactNode;
  align?: 'left' | 'right';
  width?: string;
  className?: string;
}

export const DropdownContent: React.FC<DropdownContentProps> = ({
  children,
  align = 'right',
  width = 'w-56',
  className = '',
}) => {
  const context = useContext(DropdownContext);
  if (!context) throw new Error('DropdownContent must be used within Dropdown');

  if (!context.isOpen) return null;

  const alignClass = align === 'left' ? 'left-0' : 'right-0';

  return (
    <div
      role="menu"
      tabIndex={-1}
      className={`absolute ${alignClass} mt-1.5 z-50 ${width} rounded-[var(--radius-standard)] border border-[var(--color-rule)] bg-[var(--color-paper-3)] p-1 text-[var(--color-ink)] shadow-dropdown focus:outline-none animate-zoom-in ${className}`}
    >
      {children}
    </div>
  );
};

export interface DropdownItemProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: React.ReactNode;
  shortcut?: string;
  danger?: boolean;
}

export const DropdownItem: React.FC<DropdownItemProps> = ({
  icon,
  shortcut,
  danger = false,
  children,
  className = '',
  onClick,
  disabled,
  ...props
}) => {
  const context = useContext(DropdownContext);

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (disabled) return;
    onClick?.(e);
    context?.close();
  };

  return (
    <button
      role="menuitem"
      type="button"
      disabled={disabled}
      onClick={handleClick}
      className={`group flex w-full items-center justify-between rounded-[var(--radius-sm)] px-2.5 py-1.5 text-left text-[12px] font-medium transition-colors ${
        disabled
          ? 'opacity-40 cursor-not-allowed'
          : danger
          ? 'text-red-400 hover:bg-red-500/10 hover:text-red-300'
          : 'text-[var(--color-ink)] hover:bg-[var(--color-hover)] hover:text-white'
      } focus:bg-[var(--color-hover)] focus:outline-none ${className}`}
      {...props}
    >
      <div className="flex items-center gap-2 truncate">
        {icon && <span className="shrink-0 text-[var(--color-muted)] group-hover:text-inherit" aria-hidden="true">{icon}</span>}
        <span className="truncate">{children}</span>
      </div>
      {shortcut && (
        <span className="ml-auto font-mono text-[10px] text-[var(--color-muted)] pl-2" aria-hidden="true">
          {shortcut}
        </span>
      )}
    </button>
  );
};

export const DropdownSeparator: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div role="separator" className={`my-1 h-px bg-[var(--color-rule-2)] ${className}`} />
);

export const DropdownHeader: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <div className={`px-2.5 py-1 text-[10px] font-semibold text-[var(--color-muted)] ${className}`}>
    {children}
  </div>
);
