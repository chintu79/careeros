import React from 'react';
import {
  Compass,
  CheckSquare,
  FileText,
  BookOpen,
  Sparkles,
  Bot,
  User,
  BarChart3,
  Search,
  ChevronLeft,
  ChevronRight,
  RotateCw,
  HelpCircle,
  Radar,
  Settings,
  ArrowUpRight,
} from 'lucide-react';
import { Tooltip } from '../ui/Tooltip';

interface SidebarProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onOpenCommandPalette: () => void;
  onOpenShortcuts: () => void;
  onOpenAICommand?: () => void;
  onSyncAll: () => Promise<void>;
  isSyncing: boolean;
  unreadCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  isCollapsed,
  onToggleCollapse,
  onOpenCommandPalette,
  onOpenShortcuts,
  onOpenAICommand,
  onSyncAll,
  isSyncing,
  unreadCount = 0,
}) => {
  const navSections = [
    {
      title: 'Workspace',
      items: [
        { id: 'overview', label: 'Overview', icon: BarChart3, badge: null },
        { id: 'discover', label: 'Discover', icon: Compass, badge: null },
        { id: 'tracker', label: 'Applications', icon: CheckSquare, badge: null },
        { id: 'resumes', label: 'Resume Studio', icon: FileText, badge: 'ATS' },
        { id: 'interviews', label: 'Interviews', icon: BookOpen, badge: null },
      ],
    },
    {
      title: 'Intelligence',
      items: [
        { id: 'analytics', label: 'Career Insights', icon: Sparkles, badge: null },
        { id: 'chat', label: 'AI Assistant', icon: Bot, badge: null },
      ],
    },
    {
      title: 'Personal',
      items: [
        { id: 'profile', label: 'Profile', icon: User, badge: null },
        { id: 'onboarding', label: 'Setup & Activation', icon: Sparkles, badge: null },
        { id: 'preferences', label: 'Settings', icon: Settings, badge: null },
      ],
    },
  ];

  return (
    <aside
      className={`hidden h-screen shrink-0 select-none flex-col border-r border-[var(--color-rule-2)] bg-[var(--color-sidebar)] transition-colors duration-[var(--dur-normal)] ease-[var(--ease-out)] md:flex ${
        isCollapsed ? 'w-[64px]' : 'w-[240px]'
      }`}
    >
      {/* Brand + collapse */}
      <div className={`flex h-[56px] items-center border-b border-[var(--color-rule-2)] ${isCollapsed ? 'justify-center px-2' : 'justify-between px-3.5'}`}>
        <button
          type="button"
          onClick={() => onTabChange('overview')}
          aria-label="CareerOS"
          title="CareerOS Workspace"
          className="group flex items-center gap-2.5 overflow-hidden whitespace-nowrap p-1 text-left focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] rounded-[var(--radius-sm)]"
        >
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-[var(--color-accent-bg)] border border-[var(--color-accent-border)]">
            <Radar className="h-4 w-4 text-[var(--color-accent)]" strokeWidth={2} aria-hidden="true" />
          </div>
          {!isCollapsed && (
            <span className="flex flex-col items-start leading-tight">
              <span className="flex items-center gap-1.5">
                <span className="font-display text-[14px] font-semibold text-[var(--color-ink)] ">CareerOS</span>
                <span className="rounded-[var(--radius-xs)] border border-[var(--color-rule-2)] bg-[var(--color-paper-2)] px-1.5 py-px font-mono text-[9px] text-[var(--color-muted)]">v2.9</span>
              </span>
            </span>
          )}
        </button>

        {!isCollapsed && (
          <Tooltip content="Toggle sidebar" shortcut="[">
            <button
              type="button"
              onClick={onToggleCollapse}
              className="rounded-[var(--radius-sm)] p-1 text-[var(--color-muted)] transition-colors hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              aria-expanded={!isCollapsed}
              aria-label="Collapse sidebar"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            </button>
          </Tooltip>
        )}
      </div>

      {/* Quick search & AI action */}
      <div className={`pb-1 pt-2.5 space-y-1 ${isCollapsed ? 'px-2' : 'px-3'}`}>
        {isCollapsed ? (
          <Tooltip content="Search or jump to" shortcut="⌘K" side="right">
            <button
              type="button"
              onClick={onOpenCommandPalette}
              aria-label="Search or jump to"
              className="flex w-full justify-center rounded-[var(--radius-control)] p-2 text-[var(--color-muted)] transition-colors hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
            >
              <Search className="h-4 w-4" aria-hidden="true" />
            </button>
          </Tooltip>
        ) : (
          <button
            type="button"
            onClick={onOpenCommandPalette}
            className="flex w-full items-center justify-between rounded-[var(--radius-control)] border border-[var(--color-rule-2)] bg-[var(--color-paper-2)] px-2.5 py-1.5 text-[var(--color-muted)] transition-colors hover:border-[var(--color-rule)] hover:bg-[var(--color-hover)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
          >
            <span className="flex items-center gap-2 truncate">
              <Search className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span className="text-[12px]">Search or jump to…</span>
            </span>
            <kbd className="rounded-[var(--radius-xs)] border border-[var(--color-rule-2)] bg-[var(--color-paper-3)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--color-muted)]" aria-hidden="true">
              ⌘K
            </kbd>
          </button>
        )}

        {onOpenAICommand && (
          isCollapsed ? (
            <Tooltip content="Ask CareerOS AI" shortcut="⌘J" side="right">
              <button
                type="button"
                onClick={onOpenAICommand}
                aria-label="Ask CareerOS AI"
                className="flex w-full justify-center rounded-[var(--radius-control)] p-2 text-[var(--color-muted)] transition-colors hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              >
                <Sparkles className="h-4 w-4 text-[var(--color-accent)]" aria-hidden="true" />
              </button>
            </Tooltip>
          ) : (
            <button
              type="button"
              onClick={onOpenAICommand}
              className="flex w-full items-center justify-between rounded-[var(--radius-control)] px-2.5 py-1.5 text-[var(--color-muted)] transition-colors hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
            >
              <span className="flex items-center gap-2 truncate">
                <Sparkles className="h-3.5 w-3.5 shrink-0 text-[var(--color-accent)]" aria-hidden="true" />
                <span className="text-[12px]">Ask CareerOS</span>
              </span>
              <kbd className="rounded-[var(--radius-xs)] border border-[var(--color-rule-2)] bg-[var(--color-paper-2)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--color-muted)]" aria-hidden="true">
                ⌘J
              </kbd>
            </button>
          )
        )}
      </div>

      {/* Navigation Groups */}
      <nav aria-label="Main Navigation" className="no-scrollbar flex-1 overflow-y-auto py-2.5">
        {navSections.map((section, idx) => (
          <div key={section.title} className={idx === 0 ? '' : 'mt-4'}>
            {!isCollapsed && (
              <h3 className="mb-1 px-4 text-[10px] font-semibold text-[var(--color-muted)]">
                {section.title}
              </h3>
            )}
            <div className="space-y-0.5 px-2">
              {section.items.map((item) => {
                const Icon = item.icon;
                const active = currentTab === item.id;

                const buttonElement = (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onTabChange(item.id)}
                    aria-current={active ? 'page' : undefined}
                    aria-label={isCollapsed ? item.label : undefined}
                    className={`group relative flex w-full select-none items-center rounded-[var(--radius-control)] text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--color-focus)] ${
                      isCollapsed ? 'justify-center p-2' : 'justify-between px-2.5 py-1.5'
                    } ${
                      active
                        ? 'bg-[var(--color-paper-2)] text-[var(--color-ink)] shadow-sm'
                        : 'text-[var(--color-ink-2)] hover:bg-[var(--color-hover)] hover:text-[var(--color-ink)]'
                    }`}
                  >
                    {active && (
                      <span
                        className="absolute -left-2 top-1.5 bottom-1.5 w-[2.5px] rounded-r bg-[var(--color-accent)] shadow-[0_0_8px_var(--color-accent-shadow)]"
                        aria-hidden="true"
                      />
                    )}
                    <span className="flex items-center gap-2.5 whitespace-nowrap">
                      <Icon
                        className={`h-4 w-4 shrink-0 transition-colors ${
                          active ? 'text-[var(--color-accent)]' : 'text-[var(--color-muted)] group-hover:text-[var(--color-ink)]'
                        }`}
                        strokeWidth={active ? 2 : 1.75}
                        aria-hidden="true"
                      />
                      {!isCollapsed && <span className="truncate">{item.label}</span>}
                    </span>

                    {!isCollapsed && item.badge && (
                      <span className="rounded-[var(--radius-xs)] border border-[var(--color-rule-2)] bg-[var(--color-paper-3)] px-1.5 py-px font-mono text-[9px] font-medium text-[var(--color-muted)]">
                        {item.badge}
                      </span>
                    )}
                  </button>
                );

                if (isCollapsed) {
                  return (
                    <Tooltip key={item.id} content={item.label} side="right">
                      {buttonElement}
                    </Tooltip>
                  );
                }

                return buttonElement;
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer controls */}
      <div className="shrink-0 space-y-0.5 border-t border-[var(--color-rule-2)] px-2 py-2">
        {isCollapsed ? (
          <Tooltip content={isSyncing ? 'Syncing feeds…' : 'Sync feeds'} side="right">
            <button
              type="button"
              onClick={onSyncAll}
              disabled={isSyncing}
              aria-label={isSyncing ? 'Syncing feeds' : 'Sync feeds'}
              className="flex w-full justify-center rounded-[var(--radius-control)] p-2 text-[var(--color-muted)] transition-colors hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] disabled:opacity-60"
            >
              <RotateCw className={`h-4 w-4 ${isSyncing ? 'animate-spin text-[var(--color-accent)]' : ''}`} aria-hidden="true" />
            </button>
          </Tooltip>
        ) : (
          <button
            type="button"
            onClick={onSyncAll}
            disabled={isSyncing}
            className="flex w-full items-center justify-between rounded-[var(--radius-control)] px-2.5 py-1.5 text-[12px] text-[var(--color-muted)] transition-colors hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] disabled:opacity-60"
          >
            <span className="flex items-center gap-2.5 whitespace-nowrap">
              <RotateCw className={`h-3.5 w-3.5 shrink-0 ${isSyncing ? 'animate-spin text-[var(--color-accent)]' : ''}`} aria-hidden="true" />
              <span>{isSyncing ? 'Syncing feeds…' : 'Sync feeds'}</span>
            </span>
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]/80" aria-hidden="true" />
          </button>
        )}

        {isCollapsed ? (
          <Tooltip content="Keyboard shortcuts" shortcut="?" side="right">
            <button
              type="button"
              onClick={onOpenShortcuts}
              aria-label="Keyboard shortcuts"
              className="flex w-full justify-center rounded-[var(--radius-control)] p-2 text-[var(--color-muted)] transition-colors hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
            >
              <HelpCircle className="h-4 w-4" aria-hidden="true" />
            </button>
          </Tooltip>
        ) : (
          <button
            type="button"
            onClick={onOpenShortcuts}
            className="flex w-full items-center justify-between rounded-[var(--radius-control)] px-2.5 py-1.5 text-[12px] text-[var(--color-muted)] transition-colors hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
          >
            <span className="flex items-center gap-2.5 whitespace-nowrap">
              <HelpCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>Shortcuts</span>
            </span>
            <kbd className="rounded-[var(--radius-xs)] border border-[var(--color-rule-2)] bg-[var(--color-paper-2)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--color-muted)]" aria-hidden="true">
              ?
            </kbd>
          </button>
        )}

        {/* User profile row */}
        <button
          type="button"
          onClick={() => onTabChange('profile')}
          aria-label={isCollapsed ? 'Open profile' : undefined}
          className={`flex w-full items-center whitespace-nowrap rounded-[var(--radius-control)] border-t border-[var(--color-rule-subtle)] text-left transition-colors hover:bg-[var(--color-paper-2)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] ${
            isCollapsed ? 'justify-center p-2 mt-1' : 'justify-between px-2.5 py-2 mt-1'
          }`}
        >
          <span className="flex items-center gap-2.5 whitespace-nowrap">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-paper-3)] border border-[var(--color-rule-2)] font-mono text-[10px] font-semibold text-[var(--color-accent)]">
              A
            </span>
            {!isCollapsed && (
              <span className="flex flex-col truncate">
                <span className="whitespace-nowrap text-[12px] font-medium leading-tight text-[var(--color-ink)]">Candidate</span>
                <span className="whitespace-nowrap text-[10px] leading-tight text-[var(--color-muted)]">Active</span>
              </span>
            )}
          </span>
          {!isCollapsed && <ArrowUpRight className="h-3 w-3 shrink-0 text-[var(--color-muted)]" aria-hidden="true" />}
        </button>

        {isCollapsed && (
          <Tooltip content="Expand sidebar" shortcut="[" side="right">
            <button
              type="button"
              onClick={onToggleCollapse}
              className="flex w-full justify-center rounded-[var(--radius-control)] p-2 text-[var(--color-muted)] transition-colors hover:bg-[var(--color-paper-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              aria-expanded={!isCollapsed}
              aria-label="Expand sidebar"
            >
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </Tooltip>
        )}
      </div>
    </aside>
  );
};

