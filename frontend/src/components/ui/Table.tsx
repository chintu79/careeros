import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './Button';

export const Table: React.FC<React.TableHTMLAttributes<HTMLTableElement>> = ({
  children,
  className = '',
  ...props
}) => {
  return (
    <div className="w-full overflow-x-auto rounded-[var(--radius-card)] border border-[var(--color-rule-2)] bg-[var(--color-paper)]">
      <table className={`w-full text-left text-[13px] leading-snug text-[var(--color-ink-2)] ${className}`} {...props}>
        {children}
      </table>
    </div>
  );
};

export const TableHeader: React.FC<React.HTMLAttributes<HTMLTableSectionElement>> = ({
  children,
  className = '',
  ...props
}) => {
  return (
    <thead className={`bg-[var(--color-paper-2)] text-[var(--color-muted)] font-medium border-b border-[var(--color-rule-2)] text-[11px] ${className}`} {...props}>
      {children}
    </thead>
  );
};

export const TableBody: React.FC<React.HTMLAttributes<HTMLTableSectionElement>> = ({
  children,
  className = '',
  ...props
}) => {
  return (
    <tbody className={`divide-y divide-[var(--color-rule-2)] ${className}`} {...props}>
      {children}
    </tbody>
  );
};

export const TableRow: React.FC<React.HTMLAttributes<HTMLTableRowElement>> = ({
  children,
  className = '',
  ...props
}) => {
  return (
    <tr className={`hover:bg-[var(--color-paper-2)] transition-colors ${className}`} {...props}>
      {children}
    </tr>
  );
};

export const TableHead: React.FC<React.ThHTMLAttributes<HTMLTableCellElement>> = ({
  children,
  className = '',
  ...props
}) => {
  return (
    <th className={`px-4 py-3 select-none font-medium ${className}`} {...props}>
      {children}
    </th>
  );
};

export const TableCell: React.FC<React.TdHTMLAttributes<HTMLTableCellElement>> = ({
  children,
  className = '',
  ...props
}) => {
  return (
    <td className={`px-4 py-3 align-middle leading-snug ${className}`} {...props}>
      {children}
    </td>
  );
};

export interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  className?: string;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  onPageSizeChange,
  className = '',
}) => {
  const startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  return (
    <div className={`flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3 border-t border-[var(--color-rule-2)] text-[12px] text-[var(--color-muted)] ${className}`}>
      <div className="flex items-center space-x-3 tnum">
        <span>
          Showing <strong className="text-[var(--color-ink-2)] font-mono font-medium">{startItem}</strong>,<strong className="text-[var(--color-ink-2)] font-mono font-medium">{endItem}</strong> of{' '}
          <strong className="text-[var(--color-ink-2)] font-mono font-medium">{totalItems}</strong>
        </span>

        {onPageSizeChange && (
          <div className="flex items-center space-x-1.5 pl-3 border-l border-[var(--color-rule-2)]">
            <span>Rows</span>
            <select
              aria-label="Rows per page"
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="bg-[var(--color-paper-2)] border border-[var(--color-rule)] rounded-md px-1.5 py-0.5 text-[12px] text-[var(--color-ink)] focus:outline-none focus:border-emerald-400"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>
        )}
      </div>

      <div className="flex items-center space-x-1.5">
        <Button
          variant="secondary"
          size="xs"
          disabled={currentPage <= 1}
          onClick={() => onPageChange(currentPage - 1)}
          leftIcon={<ChevronLeft className="w-3.5 h-3.5" />}
        >
          Previous
        </Button>

        <span className="px-2 text-[12px] text-[var(--color-muted)] font-mono tnum">
          {currentPage} / {Math.max(1, totalPages)}
        </span>

        <Button
          variant="secondary"
          size="xs"
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(currentPage + 1)}
          rightIcon={<ChevronRight className="w-3.5 h-3.5" />}
        >
          Next
        </Button>
      </div>
    </div>
  );
};
