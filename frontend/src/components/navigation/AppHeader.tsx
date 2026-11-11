import React, { useState } from 'react';
import {
  Menu,
  Search,
  Bell,
  PlusCircle,
  RotateCw,
  HelpCircle,
  Sparkles,
  Check,
  User,
  ChevronDown,
  LogOut
} from 'lucide-react';
import { NotificationItem } from '../../types';
import { Button } from '../ui/Button';
import { Tooltip } from '../ui/Tooltip';

interface AppHeaderProps {
  currentTab: string;
  onOpenMobileSidebar: () => void;
  onOpenCommandPalette: () => void;
  onOpenShortcuts: () => void;
  onOpenImportModal: () => void;
  onOpenAICommand?: () => void;
  onSyncAll: () => Promise<void>;
  isSyncing: boolean;
  notifications: NotificationItem[];
  unreadCount: number;
  onMarkNotificationRead: (id: number) => void;
  onMarkAllRead: () => void;
  activeUserId?: number;
  onSwitchCandidate?: (userId: number) => void;
  onLogout?: () => void;
}

const SECTION_LABEL: Record<string, string> = {
  overview: 'Overview',
  discover: 'Discover',
  tracker: 'Applications',
  resumes: 'Resume Studio',
  interviews: 'Interviews',
  analytics: 'Career Insights',
  chat: 'AI Assistant',
  profile: 'Profile',
  onboarding: 'Setup & Activation',
  sources: 'Job Sources',
  companies: 'Companies',
  preferences: 'Settings',
};

export const AppHeader: React.FC<AppHeaderProps> = ({
  currentTab,
  onOpenMobileSidebar,
  onOpenCommandPalette,
  onOpenShortcuts,
  onOpenImportModal,
  onOpenAICommand,
  onSyncAll,
  isSyncing,
  notifications,
  unreadCount,
  onMarkNotificationRead,
  onMarkAllRead,
  activeUserId = 1,
  onSwitchCandidate,
  onLogout,
}) => {
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const isDev = Boolean(import.meta.env.DEV);

  return (
    <header
      role="banner"
      className="relative z-20 flex h-[56px] items-center justify-between border-b border-[var(--color-rule-2)] bg-[var(--color-sidebar)] px-3 sm:px-6 shrink-0"
    >
      {/* Breadcrumb Hierarchy */}
      <div className="flex min-w-0 items-center gap-2.5 pr-2">
        <button
          type="button"
          onClick={onOpenMobileSidebar}
          className="shrink-0 rounded-[var(--radius-sm)] p-1.5 text-[var(--color-muted)] transition-colors hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] md:hidden"
          aria-label="Open navigation menu"
        >
          <Menu className="h-4 w-4" aria-hidden="true" />
        </button>

        <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2">
          <span className="hidden text-[12px] font-medium text-[var(--color-muted)] sm:inline">CareerOS</span>
          <span className="hidden text-[var(--color-rule-2)] text-[12px] sm:inline" aria-hidden="true">/</span>
          <h2 className="truncate text-[13px] font-semibold text-[var(--color-ink)] ">
            {SECTION_LABEL[currentTab] || 'CareerOS'}
          </h2>
        </nav>
      </div>

      {/* Action Controls */}
      <div className="flex shrink-0 items-center gap-1.5">
        {onOpenAICommand && (
          <button
            type="button"
            onClick={onOpenAICommand}
            className="hidden min-h-[32px] items-center gap-1.5 rounded-[var(--radius-control)] border border-[var(--color-rule-2)] bg-[var(--color-paper-2)] px-2.5 text-[12px] font-medium text-[var(--color-ink)] transition-colors hover:border-[var(--color-rule)] hover:bg-[var(--color-hover)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] sm:inline-flex"
          >
            <Sparkles className="h-3.5 w-3.5 text-[var(--color-accent)] shrink-0" strokeWidth={1.75} aria-hidden="true" />
            <span className="whitespace-nowrap">Ask AI</span>
            <kbd className="hidden rounded-[var(--radius-xs)] border border-[var(--color-rule-2)] bg-[var(--color-paper-3)] px-1 py-0.2 font-mono text-[9px] text-[var(--color-muted)] lg:inline" aria-hidden="true">⌘J</kbd>
          </button>
        )}

        <button
          type="button"
          onClick={onOpenCommandPalette}
          className="inline-flex min-h-[32px] items-center gap-1.5 rounded-[var(--radius-control)] border border-[var(--color-rule-2)] bg-[var(--color-paper-2)] px-2.5 text-[var(--color-muted)] transition-colors hover:border-[var(--color-rule)] hover:bg-[var(--color-hover)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
          aria-label="Search or jump to a page"
        >
          <Search className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden="true" />
          <span className="hidden text-[12px] md:inline">Search</span>
          <kbd className="hidden rounded-[var(--radius-xs)] border border-[var(--color-rule-2)] bg-[var(--color-paper-3)] px-1 py-0.2 font-mono text-[9px] text-[var(--color-muted)] lg:inline" aria-hidden="true">⌘K</kbd>
        </button>

        <span className="mx-1 hidden h-4 w-px bg-[var(--color-rule-2)] sm:block" aria-hidden="true" />

        <Button
          variant="secondary"
          size="sm"
          onClick={onOpenImportModal}
          leftIcon={<PlusCircle className="h-3.5 w-3.5" />}
          className="hidden sm:inline-flex"
        >
          Import job
        </Button>

        <Tooltip content={isSyncing ? "Syncing feeds…" : "Sync feeds"}>
          <button
            type="button"
            onClick={onSyncAll}
            disabled={isSyncing}
            aria-label={isSyncing ? 'Syncing feeds' : 'Sync feeds'}
            className={`rounded-[var(--radius-control)] p-1.5 transition-colors focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] ${
              isSyncing
                ? 'bg-[var(--color-paper-2)] text-[var(--color-accent)]'
                : 'text-[var(--color-muted)] hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)]'
            }`}
          >
            <RotateCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} aria-hidden="true" />
          </button>
        </Tooltip>

        {/* User / Candidate Account Switcher Menu */}
        {(onSwitchCandidate || onLogout) && (
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowUserMenu(!showUserMenu)}
              aria-expanded={showUserMenu}
              aria-haspopup="true"
              className="inline-flex min-h-[32px] items-center gap-1.5 rounded-[var(--radius-control)] border border-[var(--color-rule-2)] bg-[var(--color-paper-2)] px-2.5 py-1 text-[11px] font-medium text-[var(--color-ink-2)] transition-colors hover:border-[var(--color-rule)] hover:bg-[var(--color-hover)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              title={isDev ? "Candidate profile context (Dev mode)" : "Account menu"}
            >
              <User className="h-3.5 w-3.5 text-[var(--color-accent)]" aria-hidden="true" />
              <span className="hidden sm:inline font-mono font-medium">
                {isDev 
                  ? (activeUserId === 1 ? 'Candidate A (User 1)' : 'Candidate B (User 2)')
                  : (activeUserId === 1 ? 'Candidate One' : `User ${activeUserId}`)}
              </span>
              <span className="sm:hidden font-mono">U{activeUserId}</span>
              <ChevronDown className="h-3 w-3 text-[var(--color-muted)]" aria-hidden="true" />
            </button>

            {showUserMenu && (
              <>
                <div className="fixed inset-0 z-30" onClick={() => setShowUserMenu(false)} aria-hidden="true" />
                <div
                  role="menu"
                  className="absolute right-0 z-40 mt-1.5 w-64 rounded-[var(--radius-standard)] border border-[var(--color-rule)] bg-[var(--color-paper-3)] p-2 shadow-dropdown animate-zoom-in text-[12px]"
                >
                  <div className="px-2 py-1 text-[10px] font-semibold text-[var(--color-muted)]">
                    {isDev ? 'Candidate Profile Context (Dev)' : 'Active Account'}
                  </div>

                  {/* Dev-only candidate switching options */}
                  {isDev && onSwitchCandidate && (
                    <div className="space-y-1 mt-1">
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setShowUserMenu(false);
                          onSwitchCandidate(1);
                        }}
                        className={`flex w-full items-center justify-between whitespace-nowrap rounded-[var(--radius-sm)] px-2.5 py-2 text-left transition-colors ${
                          activeUserId === 1
                            ? 'bg-[var(--color-accent-bg)] text-[var(--color-accent)] font-medium border border-[var(--color-accent-border)]'
                            : 'text-[var(--color-ink)] hover:bg-[var(--color-hover)]'
                        }`}
                      >
                        <span className="font-semibold">Candidate One</span>
                        {activeUserId === 1 && <Check className="h-3.5 w-3.5 text-[var(--color-accent)]" />}
                      </button>

                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setShowUserMenu(false);
                          onSwitchCandidate(2);
                        }}
                        className={`flex w-full items-center justify-between whitespace-nowrap rounded-[var(--radius-sm)] px-2.5 py-2 text-left transition-colors ${
                          activeUserId === 2
                            ? 'bg-[var(--color-accent-bg)] text-[var(--color-accent)] font-medium border border-[var(--color-accent-border)]'
                            : 'text-[var(--color-ink)] hover:bg-[var(--color-hover)]'
                        }`}
                      >
                        <span className="font-semibold">Candidate B (Demo)</span>
                        {activeUserId === 2 && <Check className="h-3.5 w-3.5 text-[var(--color-accent)]" />}
                      </button>
                    </div>
                  )}

                  {!isDev && (
                    <div className="px-2 py-2">
                      <div className="font-semibold text-[var(--color-ink)]">Candidate One</div>
                      <div className="text-[11px] text-[var(--color-muted)] font-mono">Verified Candidate Account</div>
                    </div>
                  )}

                  {onLogout && (
                    <div className="mt-2 border-t border-[var(--color-rule-2)] pt-1">
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setShowUserMenu(false);
                          onLogout();
                        }}
                        className="flex w-full items-center gap-2 rounded-[var(--radius-sm)] px-2.5 py-2 text-left text-red-400 hover:bg-red-500/10 transition-colors"
                      >
                        <LogOut className="h-3.5 w-3.5 text-red-400" aria-hidden="true" />
                        <span>Sign out / Reset Session</span>
                      </button>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {/* Notifications Popover */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative rounded-[var(--radius-control)] p-1.5 text-[var(--color-muted)] transition-colors hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
            aria-expanded={showNotifications}
            aria-haspopup="true"
            aria-label={unreadCount > 0 ? `${unreadCount} notifications` : 'Notifications'}
          >
            <Bell className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
            {unreadCount > 0 && (
              <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-[var(--color-accent)] shadow-[0_0_6px_var(--color-accent-shadow)]" aria-hidden="true" />
            )}
          </button>

          {showNotifications && (
            <>
              <div className="fixed inset-0 z-30" onClick={() => setShowNotifications(false)} aria-hidden="true" />
              <div
                role="region"
                aria-label="Notifications panel"
                className="absolute right-0 z-40 mt-2 w-[340px] max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-[var(--radius-standard)] border border-[var(--color-rule)] bg-[var(--color-paper-3)] shadow-dropdown animate-zoom-in"
              >
                <div className="flex items-center justify-between border-b border-[var(--color-rule-2)] px-4 py-3">
                  <span className="text-[12px] font-semibold text-[var(--color-ink)]">
                    Notifications
                  </span>
                  {unreadCount > 0 && (
                    <button
                      type="button"
                      onClick={onMarkAllRead}
                      className="rounded px-1.5 py-0.5 text-[11px] font-medium text-[var(--color-accent)] hover:underline transition-colors focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
                    >
                      Mark all read
                    </button>
                  )}
                </div>

                <div className="max-h-80 divide-y divide-[var(--color-rule-2)] overflow-y-auto" role="feed" aria-label="Recent notifications">
                  {notifications.length === 0 ? (
                    <div className="p-8 text-center text-[12px] text-[var(--color-muted)]">
                      No new notifications.
                    </div>
                  ) : (
                    notifications.map((n) => (
                      <button
                        key={n.id}
                        type="button"
                        onClick={() => onMarkNotificationRead(n.id)}
                        aria-label={`${n.title}: ${n.message}${!n.is_read ? ' (unread)' : ''}`}
                        className={`flex w-full items-start justify-between gap-3 p-3.5 text-left text-[12px] transition-colors hover:bg-[var(--color-hover)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--color-focus)] ${
                          !n.is_read ? 'bg-[var(--color-paper-2)]/80' : ''
                        }`}
                      >
                        <span className="min-w-0">
                          <span className="block truncate font-medium text-[var(--color-ink)]">{n.title}</span>
                          <span className="mt-0.5 block text-[11px] leading-relaxed text-[var(--color-ink-2)] line-clamp-2">
                            {n.message}
                          </span>
                          <span className="mt-1 block font-mono text-[10px] text-[var(--color-muted)]">
                            {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </span>
                        {!n.is_read ? (
                          <span className="mt-1.5 h-1.5 w-1.5 rounded-full shrink-0 bg-[var(--color-accent)]" aria-label="Unread" />
                        ) : (
                          <Check className="mt-1 h-3.5 w-3.5 shrink-0 text-[var(--color-muted)]" aria-hidden="true" />
                        )}
                      </button>
                    ))
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        <Tooltip content="Keyboard shortcuts" shortcut="?">
          <button
            type="button"
            onClick={onOpenShortcuts}
            className="hidden rounded-[var(--radius-control)] p-1.5 text-[var(--color-muted)] transition-colors hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] lg:inline-flex"
            aria-label="View keyboard shortcuts"
          >
            <HelpCircle className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
          </button>
        </Tooltip>
      </div>
    </header>
  );
};

