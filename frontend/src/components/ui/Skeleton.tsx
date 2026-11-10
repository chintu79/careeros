import React from 'react';

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'rectangular' | 'circular' | 'rounded';
}

export const Skeleton: React.FC<SkeletonProps> = ({
  variant = 'rounded',
  className = '',
  ...props
}) => {
  const variantClasses = {
    rectangular: 'rounded-[var(--radius-xs)]',
    circular: 'rounded-full',
    rounded: 'rounded-[var(--radius-control)]',
  }[variant];

  return (
    <div
      className={`bg-white/[0.06] animate-pulse ${variantClasses} ${className}`}
      {...props}
    />
  );
};

export const CardSkeleton: React.FC = () => {
  return (
    <div className="rounded-[var(--radius-card)] border border-slate-800 bg-slate-900/80 p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3.5">
          <Skeleton variant="rounded" className="w-12 h-12" />
          <div className="space-y-2">
            <Skeleton className="w-28 h-3.5" />
            <Skeleton className="w-48 h-5" />
          </div>
        </div>
        <Skeleton variant="rounded" className="w-16 h-6" />
      </div>

      <div className="flex items-center space-x-3 pt-2">
        <Skeleton className="w-24 h-4" />
        <Skeleton className="w-20 h-4" />
        <Skeleton className="w-24 h-4" />
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-slate-800/80">
        <div className="flex items-center space-x-2">
          <Skeleton className="w-16 h-5 rounded-md" />
          <Skeleton className="w-20 h-5 rounded-md" />
        </div>
        <div className="flex items-center space-x-2">
          <Skeleton className="w-24 h-7 rounded-[var(--radius-card)]" />
          <Skeleton className="w-20 h-7 rounded-[var(--radius-card)]" />
        </div>
      </div>
    </div>
  );
};

export const TableRowSkeleton: React.FC<{ columns?: number }> = ({ columns = 5 }) => {
  return (
    <tr className="border-b border-slate-800/60 animate-pulse">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="p-3.5">
          <Skeleton className="h-4 w-full max-w-[120px]" />
        </td>
      ))}
    </tr>
  );
};
