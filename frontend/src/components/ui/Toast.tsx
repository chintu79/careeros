import React, { useState, useEffect, createContext, useContext } from 'react';
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info' | 'warn';

export interface ToastItem {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
}

interface ToastContextType {
  toasts: ToastItem[];
  addToast: (toast: Omit<ToastItem, 'id'>) => void;
  removeToast: (id: string) => void;
  toast: {
    success: (message: string, title?: string) => void;
    error: (message: string, title?: string) => void;
    info: (message: string, title?: string) => void;
    warn: (message: string, title?: string) => void;
  };
}

const ToastContext = createContext<ToastContextType | null>(null);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  const addToast = (item: Omit<ToastItem, 'id'>) => {
    const id = Math.random().toString(36).substring(2, 9);
    const newToast: ToastItem = { ...item, id };
    setToasts(prev => [...prev, newToast]);

    const duration = item.duration ?? 4000;
    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }
  };

  const toast = {
    success: (message: string, title?: string) => addToast({ type: 'success', message, title }),
    error: (message: string, title?: string) => addToast({ type: 'error', message, title }),
    info: (message: string, title?: string) => addToast({ type: 'info', message, title }),
    warn: (message: string, title?: string) => addToast({ type: 'warn', message, title }),
  };

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast, toast }}>
      {children}
      <div
        aria-live="polite"
        role="region"
        aria-label="Notifications"
        className="fixed bottom-4 right-4 z-[var(--z-toast)] flex flex-col gap-2 max-w-sm w-full pointer-events-none"
      >
        {toasts.map(t => (
          <ToastCard key={t.id} toast={t} onClose={() => removeToast(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

const ToastCard: React.FC<{ toast: ToastItem; onClose: () => void }> = ({ toast, onClose }) => {
  const icons = {
    success: <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />,
    error: <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />,
    info: <Info className="h-4 w-4 text-sky-400 shrink-0" />,
    warn: <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />,
  };

  const borderColors = {
    success: 'border-emerald-500/30',
    error: 'border-red-500/30',
    info: 'border-sky-500/30',
    warn: 'border-amber-500/30',
  };

  return (
    <div
      role="status"
      className={`pointer-events-auto flex items-start gap-3 rounded-[var(--radius-standard)] border ${borderColors[toast.type]} bg-[var(--color-paper-3)] p-3.5 shadow-modal animate-slide-down`}
    >
      {icons[toast.type]}
      <div className="flex-1 min-w-0 space-y-0.5">
        {toast.title && (
          <p className="text-[13px] font-semibold text-[var(--color-ink)]">
            {toast.title}
          </p>
        )}
        <p className="text-[12px] leading-relaxed text-[var(--color-ink-2)]">
          {toast.message}
        </p>
      </div>
      <button
        type="button"
        onClick={onClose}
        aria-label="Dismiss notification"
        className="rounded p-1 text-[var(--color-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-ink)] transition-colors focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
};
