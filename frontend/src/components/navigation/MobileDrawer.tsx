import React, { useEffect, useRef } from 'react';
import {
  X,
  Compass,
  CheckSquare,
  FileText,
  BookOpen,
  Sparkles,
  Bot,
  User,
  BarChart3,
  RotateCw,
  PlusCircle,
  Radar,
  Settings,
} from 'lucide-react';
import { trapFocus, saveActiveElement, restoreActiveElement, focusFirstElement } from '../../utils/focusTrap';

interface MobileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  currentTab: string;
  onTabChange: (tab: string) => void;
  onOpenImport: () => void;
  onOpenShortcuts: () => void;
  onSyncAll: () => Promise<void>;
  isSyncing: boolean;
}

export const MobileDrawer: React.FC<MobileDrawerProps> = ({
  isOpen,
  onClose,
  currentTab,
  onTabChange,
  onOpenImport,
  onOpenShortcuts,
  onSyncAll,
  isSyncing,
}) => {
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    saveActiveElement();

    if (drawerRef.current) {
      focusFirstElement(drawerRef.current);
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      } else if (e.key === 'Tab' && drawerRef.current) {
        trapFocus(drawerRef.current, e);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      restoreActiveElement();
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const navItems = [
    {
      section: 'Workspace',
      items: [
        { id: 'overview', label: 'Overview', icon: BarChart3 },
        { id: 'discover', label: 'Discover', icon: Compass },
        { id: 'tracker', label: 'Applications', icon: CheckSquare },
        { id: 'resumes', label: 'Resume Studio', icon: FileText, badge: 'ATS' },
        { id: 'interviews', label: 'Interviews', icon: BookOpen },
      ],
    },
    {
      section: 'Intelligence',
      items: [
        { id: 'analytics', label: 'Career Insights', icon: Sparkles },
        { id: 'chat', label: 'AI Assistant', icon: Bot },
      ],
    },
    {
      section: 'Personal',
      items: [
        { id: 'profile', label: 'Profile', icon: User },
        { id: 'onboarding', label: 'Setup & Activation', icon: Sparkles },
        { id: 'preferences', label: 'Settings', icon: Settings },
      ],
    },
  ];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Navigation menu"
      className="fixed inset-0 z-50 flex bg-black/75 backdrop-blur-[2px] md:hidden animate-fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={drawerRef}
        tabIndex={-1}
        className="flex h-full w-72 max-w-[85vw] flex-col justify-between border-r border-[var(--color-rule)] bg-[var(--color-paper-3)] shadow-modal animate-slide-down outline-none"
      >
        {/* Header */}
        <div>
          <div className="flex h-[56px] items-center justify-between border-b border-[var(--color-rule-2)] px-4">
            <button
              type="button"
              onClick={() => {
                onTabChange('overview');
                onClose();
              }}
              className="flex items-center gap-2.5 text-left focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] rounded-[var(--radius-sm)]"
              aria-label="CareerOS, go to Overview"
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-control)] bg-[var(--color-accent-bg)] border border-[var(--color-accent-border)]">
                <Radar className="h-4 w-4 text-[var(--color-accent)]" strokeWidth={2} aria-hidden="true" />
              </div>
              <span className="flex items-baseline gap-1.5">
                <span className="font-display text-[14px] font-semibold text-[var(--color-ink)]">CareerOS</span>
                <span className="rounded-[var(--radius-xs)] border border-[var(--color-rule-2)] bg-[var(--color-paper-2)] px-1.5 py-px font-mono text-[9px] text-[var(--color-muted)]">v2.9</span>
              </span>
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close navigation menu"
              className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] text-[var(--color-muted)] transition-colors hover:bg-[var(--color-hover)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>

          {/* Navigation Links */}
          <nav aria-label="Main navigation" className="max-h-[70vh] space-y-4 overflow-y-auto p-3">
            {navItems.map((group) => (
              <div key={group.section} className="space-y-1">
                <h3 className="px-2 text-[10px] font-semibold text-[var(--color-muted)]">
                  {group.section}
                </h3>
                <div className="space-y-0.5">
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const active = currentTab === item.id;

                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => {
                          onTabChange(item.id);
                          onClose();
                        }}
                        aria-current={active ? 'page' : undefined}
                        className={`flex min-h-[44px] w-full items-center justify-between rounded-[var(--radius-control)] px-3 py-2 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-[var(--color-focus)] ${
                          active
                            ? 'bg-[var(--color-paper-2)] text-[var(--color-ink)] shadow-sm'
                            : 'text-[var(--color-ink-2)] hover:bg-[var(--color-hover)] hover:text-[var(--color-ink)]'
                        }`}
                      >
                        <span className="flex items-center gap-2.5">
                          <Icon className={`h-4 w-4 ${active ? 'text-[var(--color-accent)]' : 'text-[var(--color-muted)]'}`} strokeWidth={active ? 2 : 1.75} aria-hidden="true" />
                          <span>{item.label}</span>
                        </span>
                        {item.badge && (
                          <span className="rounded-[var(--radius-xs)] border border-[var(--color-rule-2)] bg-[var(--color-paper-3)] px-1.5 py-px font-mono text-[9px] font-medium text-[var(--color-muted)]">
                            {item.badge}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
        </div>

        {/* Footer Actions */}
        <div className="space-y-2 border-t border-[var(--color-rule-2)] p-3">
          <button
            type="button"
            onClick={() => {
              onClose();
              onOpenImport();
            }}
            className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-[var(--radius-control)] border border-[var(--color-rule-2)] bg-[var(--color-paper-2)] px-3 text-[13px] font-medium text-[var(--color-ink)] transition-colors hover:bg-[var(--color-hover)] hover:border-[var(--color-rule)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
          >
            <PlusCircle className="h-4 w-4 text-[var(--color-accent)]" aria-hidden="true" />
            <span>Import job posting</span>
          </button>

          <button
            type="button"
            onClick={onSyncAll}
            disabled={isSyncing}
            className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-[var(--radius-control)] border border-[var(--color-rule-2)] bg-[var(--color-paper-2)] px-3 text-[13px] font-medium text-[var(--color-ink)] transition-colors hover:bg-[var(--color-hover)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] disabled:opacity-60"
          >
            <RotateCw className={`h-4 w-4 ${isSyncing ? 'animate-spin text-[var(--color-accent)]' : ''}`} aria-hidden="true" />
            <span>{isSyncing ? 'Syncing…' : 'Sync feeds'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

