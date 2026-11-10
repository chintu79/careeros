import React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  isInteractive?: boolean;
  selected?: boolean;
}

export const Card: React.FC<CardProps> = ({
  isInteractive = false,
  selected = false,
  children,
  className = '',
  ...props
}) => {
  const interactiveClasses = isInteractive
    ? 'cursor-pointer hover:bg-[var(--color-paper-3)] hover:border-[var(--color-rule)] hover:shadow-dropdown'
    : '';

  const selectedClasses = selected
    ? 'border-[var(--color-accent-border)] bg-[var(--color-paper-3)]'
    : 'border-[var(--color-rule-2)] bg-[var(--color-paper-2)]';

  return (
    <div
      className={`rounded-[var(--radius-card)] border shadow-card transition-colors duration-150 ease-out ${selectedClasses} ${interactiveClasses} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

export interface CardHeaderProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
}

export const CardHeader: React.FC<CardHeaderProps> = ({
  title,
  subtitle,
  action,
  children,
  className = '',
  ...props
}) => {
  return (
    <div className={`flex items-start justify-between gap-3 border-b border-[var(--color-rule-2)] px-4 py-3.5 ${className}`} {...props}>
      {(title || subtitle) ? (
        <div className="min-w-0 space-y-0.5">
          {title && (
            <h3 className="section-title">{title}</h3>
          )}
          {subtitle && (
            <p className="text-[12px] font-normal leading-relaxed text-[var(--color-muted)]">{subtitle}</p>
          )}
        </div>
      ) : children}
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
};

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className = '',
  ...props
}) => {
  return (
    <div className={`p-4 ${className}`} {...props}>
      {children}
    </div>
  );
};

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  children,
  className = '',
  ...props
}) => {
  return (
    <div className={`flex items-center justify-between gap-2 border-t border-[var(--color-rule-2)] px-4 py-3 ${className}`} {...props}>
      {children}
    </div>
  );
};
