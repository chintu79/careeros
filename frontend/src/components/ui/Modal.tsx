import React, { useEffect, useRef, useId } from 'react';
import { X } from 'lucide-react';
import { trapFocus, saveActiveElement, restoreActiveElement, focusFirstElement } from '../../utils/focusTrap';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  description?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | '4xl' | '5xl';
  children: React.ReactNode;
  footer?: React.ReactNode;
  showCloseButton?: boolean;
  className?: string;
  headerAction?: React.ReactNode;
  ariaLabel?: string;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  description,
  size = 'lg',
  children,
  footer,
  showCloseButton = true,
  className = '',
  headerAction,
  ariaLabel,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const subtitleId = useId();

  // Focus management: save previous active element on open, trap Tab, restore on close
  useEffect(() => {
    if (!isOpen) return;

    saveActiveElement();

    if (modalRef.current) {
      focusFirstElement(modalRef.current);
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      } else if (e.key === 'Tab' && modalRef.current) {
        trapFocus(modalRef.current, e);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      restoreActiveElement();
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const effectiveSubtitle = subtitle || description;

  const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
    '3xl': 'max-w-3xl',
    '4xl': 'max-w-4xl',
    '5xl': 'max-w-5xl',
  }[size];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? titleId : undefined}
      aria-describedby={effectiveSubtitle ? subtitleId : undefined}
      aria-label={!title && ariaLabel ? ariaLabel : undefined}
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-[var(--color-paper-3)] backdrop-blur-[2px] overscroll-contain animate-fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        ref={modalRef}
        tabIndex={-1}
        className={`relative w-full ${sizeClasses} bg-[var(--color-paper-2)] border border-[var(--color-rule)] rounded-[var(--radius-card)] flex flex-col max-h-[92vh] overflow-hidden outline-none animate-zoom-in ${className}`}
      >
        {/* Header */}
        {(title || showCloseButton || headerAction) && (
          <div className="px-4 sm:px-5 py-4 border-b border-[var(--color-rule-2)] flex items-start justify-between gap-3 shrink-0">
            <div className="min-w-0">
              {title && (
                <h3 id={titleId} className="text-[15px] font-semibold text-[var(--color-ink)] flex items-center space-x-2">
                  {title}
                </h3>
              )}
              {effectiveSubtitle && (
                <p id={subtitleId} className="text-[12px] text-[var(--color-muted)] mt-1 leading-relaxed">{effectiveSubtitle}</p>
              )}
            </div>

            <div className="flex items-center space-x-2 shrink-0">
              {headerAction}
              {showCloseButton && (
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close dialog"
                  className="p-1.5 rounded-md text-[var(--color-muted)] hover:text-[var(--color-ink)] hover:bg-[var(--color-paper-2)] focus-visible:ring-2 focus-visible:ring-emerald-400 transition min-h-[28px] min-w-[28px] flex items-center justify-center"
                >
                  <X className="w-4 h-4" aria-hidden="true" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Modal Body */}
        <div
          tabIndex={0}
          role="region"
          aria-label={title ? `${title} content` : 'Dialog content'}
          className="flex-1 overflow-y-auto overscroll-contain focus:outline-none focus-visible:ring-1 focus-visible:ring-emerald-400"
        >
          {children}
        </div>

        {/* Modal Footer */}
        {footer && (
          <div className="px-4 sm:px-5 py-3.5 border-t border-[var(--color-rule-2)] bg-[var(--color-paper-3)] shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};
